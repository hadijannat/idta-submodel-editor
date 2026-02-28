/**
 * Docker service health checking utilities.
 *
 * Provides health checks for dataspace services (BaSyx, EDC, DTR, Vault)
 * and other Docker-based dependencies.
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);
const VAULT_HOST_PORT = process.env.VAULT_HOST_PORT || '8200';

// ============================================================================
// Types
// ============================================================================

export interface ServiceHealth {
  name: string;
  status: 'healthy' | 'unhealthy' | 'unknown';
  url?: string;
  latency_ms?: number;
  error?: string;
  container_status?: string;
}

export interface HealthCheckOptions {
  /**
   * Timeout for each health check in milliseconds.
   * @default 5000
   */
  timeout?: number;

  /**
   * Whether to check Docker container status.
   * @default true
   */
  checkContainers?: boolean;
}

// ============================================================================
// Service Definitions
// ============================================================================

const CORE_SERVICES = {
  backend: {
    name: 'Backend API',
    url: 'http://localhost:8000/health',
    container: 'backend',
  },
  frontend: {
    name: 'Frontend',
    // Use Vite client endpoint instead of root HTML so tests only start after
    // the dev server is fully ready to serve transformed modules.
    url: 'http://localhost:8080/@vite/client',
    container: 'frontend',
  },
};

const DATASPACE_SERVICES = {
  basyx_aas_server: {
    name: 'BaSyx AAS Server',
    url: 'http://localhost:4001/shells',
    container: 'basyx-aas-server',
  },
  basyx_registry: {
    name: 'BaSyx Registry',
    url: 'http://localhost:4002/api/v1/registry',
    container: 'basyx-registry',
  },
  dtr: {
    name: 'Digital Twin Registry',
    url: 'http://localhost:4003/actuator/health',
    container: 'dtr',
  },
  edc_control_plane: {
    name: 'EDC Control Plane',
    url: 'http://localhost:19192/api/management/v2/catalog',
    container: 'edc-control-plane',
  },
  edc_data_plane: {
    name: 'EDC Data Plane',
    url: 'http://localhost:19291/api/public',
    container: 'edc-data-plane',
  },
  vault: {
    name: 'HashiCorp Vault',
    url: `http://localhost:${VAULT_HOST_PORT}/v1/sys/health`,
    container: 'vault',
  },
  mnestix: {
    name: 'Mnestix AAS Browser',
    url: 'http://localhost:3001',
    container: 'mnestix',
  },
  postgres: {
    name: 'PostgreSQL',
    url: '', // No HTTP endpoint, check container only
    container: 'postgres-dataspace',
  },
};

const MAGIC_IMPORT_SERVICES = {
  redis: {
    name: 'Redis',
    url: '', // No HTTP endpoint
    container: 'redis',
  },
  celery_worker: {
    name: 'Celery Worker',
    url: '', // No HTTP endpoint
    container: 'celery-worker',
  },
};

const PLC_SERVICES = {
  plc4x_bridge: {
    name: 'PLC4X Bridge',
    url: 'http://localhost:8090/actuator/health',
    container: 'plc4x-bridge',
  },
};

// ============================================================================
// Health Check Functions
// ============================================================================

/**
 * Check health of a single service via HTTP.
 */
async function checkHttpHealth(
  url: string,
  timeout: number
): Promise<{ healthy: boolean; latency_ms: number; error?: string }> {
  const start = Date.now();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    const response = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    return {
      healthy: response.ok || response.status === 401 || response.status === 403,
      latency_ms: Date.now() - start,
    };
  } catch (error: unknown) {
    const err = error as { message?: string };
    return {
      healthy: false,
      latency_ms: Date.now() - start,
      error: err.message ?? 'Unknown error',
    };
  }
}

/**
 * Check Docker container status.
 */
async function checkContainerStatus(
  containerName: string
): Promise<{ running: boolean; status?: string; error?: string }> {
  const inspectStatus = async (
    target: string
  ): Promise<{ running: boolean; status?: string }> => {
    const { stdout } = await execAsync(
      `docker inspect --format='{{.State.Status}}' ${target}`,
      { timeout: 5000 }
    );
    const status = stdout.trim();
    return {
      running: status === 'running',
      status,
    };
  };

  try {
    return await inspectStatus(containerName);
  } catch (error: unknown) {
    // Compose often prefixes container names with the project name.
    // Resolve by compose service label first, then by a loose name match.
    try {
      const { stdout } = await execAsync(
        `docker ps -aq --filter "label=com.docker.compose.service=${containerName}" | head -n 1`,
        { timeout: 5000 }
      );
      const containerId = stdout.trim();
      if (containerId) {
        return await inspectStatus(containerId);
      }
    } catch {
      // Ignore and continue to next fallback.
    }

    try {
      const { stdout } = await execAsync(
        `docker ps -aq --filter "name=${containerName}" | head -n 1`,
        { timeout: 5000 }
      );
      const containerId = stdout.trim();
      if (containerId) {
        return await inspectStatus(containerId);
      }
    } catch {
      // Ignore and fall through to not-found error.
    }

    const err = error as { message?: string };
    return {
      running: false,
      error: err.message?.includes('No such object')
        ? 'Container not found'
        : err.message ?? 'Unknown error',
    };
  }
}

/**
 * Check health of a service.
 */
async function checkService(
  service: { name: string; url: string; container: string },
  options: HealthCheckOptions
): Promise<ServiceHealth> {
  const timeout = options.timeout ?? 5000;
  const result: ServiceHealth = {
    name: service.name,
    status: 'unknown',
    url: service.url || undefined,
  };

  // Check HTTP health first if URL provided (preferred method)
  if (service.url) {
    const httpHealth = await checkHttpHealth(service.url, timeout);
    result.latency_ms = httpHealth.latency_ms;

    if (httpHealth.healthy) {
      result.status = 'healthy';
      return result; // HTTP is healthy, no need to check containers
    }
  }

  // If HTTP check failed or no URL, check container status
  if (options.checkContainers !== false && service.container) {
    const containerHealth = await checkContainerStatus(service.container);
    result.container_status = containerHealth.status;

    if (containerHealth.running) {
      // Container is running but HTTP might not be ready yet
      if (!service.url) {
        result.status = 'healthy';
      }
      // Keep the HTTP error if URL check failed
    } else if (!service.url) {
      // No URL and container not running
      result.status = 'unhealthy';
      result.error = containerHealth.error ?? 'Container not running';
    }
  }

  // If we still have no status but HTTP check was attempted and failed
  if (result.status === 'unknown' && service.url) {
    result.status = 'unhealthy';
  }

  return result;
}

// ============================================================================
// Public API
// ============================================================================

/**
 * Check health of core services (backend, frontend).
 */
export async function checkCoreServices(
  options: HealthCheckOptions = {}
): Promise<ServiceHealth[]> {
  const results = await Promise.all(
    Object.values(CORE_SERVICES).map((service) => checkService(service, options))
  );
  return results;
}

/**
 * Check health of dataspace services.
 */
export async function checkDataspaceServices(
  options: HealthCheckOptions = {}
): Promise<ServiceHealth[]> {
  const results = await Promise.all(
    Object.values(DATASPACE_SERVICES).map((service) => checkService(service, options))
  );
  return results;
}

/**
 * Check health of magic import services.
 */
export async function checkMagicImportServices(
  options: HealthCheckOptions = {}
): Promise<ServiceHealth[]> {
  const results = await Promise.all(
    Object.values(MAGIC_IMPORT_SERVICES).map((service) => checkService(service, options))
  );
  return results;
}

/**
 * Check health of PLC4X bridge services.
 */
export async function checkPlcServices(
  options: HealthCheckOptions = {}
): Promise<ServiceHealth[]> {
  const results = await Promise.all(
    Object.values(PLC_SERVICES).map((service) => checkService(service, options))
  );
  return results;
}

/**
 * Check all services for a given profile.
 */
export async function checkServicesForProfile(
  profile: 'default' | 'magic-import' | 'dataspace' | 'plc',
  options: HealthCheckOptions = {}
): Promise<ServiceHealth[]> {
  const results: ServiceHealth[] = [];

  // Core services are always checked
  results.push(...(await checkCoreServices(options)));

  // Profile-specific services
  switch (profile) {
    case 'magic-import':
      results.push(...(await checkMagicImportServices(options)));
      break;
    case 'dataspace':
      results.push(...(await checkDataspaceServices(options)));
      break;
    case 'plc':
      results.push(...(await checkDataspaceServices(options)));
      results.push(...(await checkPlcServices(options)));
      break;
  }

  return results;
}

// ============================================================================
// Waiting Utilities
// ============================================================================

/**
 * Wait for services to become healthy.
 *
 * @param checkFn - Function that returns service health status
 * @param timeoutMs - Maximum time to wait
 * @param intervalMs - Time between checks
 */
export async function waitForServices(
  checkFn: () => Promise<ServiceHealth[]>,
  timeoutMs: number = 120000,
  intervalMs: number = 2000
): Promise<ServiceHealth[]> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    const services = await checkFn();
    const allHealthy = services.every((s) => s.status === 'healthy');

    if (allHealthy) {
      return services;
    }

    // Log unhealthy services
    const unhealthy = services.filter((s) => s.status !== 'healthy');
    console.log(
      `Waiting for services: ${unhealthy.map((s) => s.name).join(', ')}`
    );

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  // Final check
  const services = await checkFn();
  const unhealthy = services.filter((s) => s.status !== 'healthy');

  if (unhealthy.length > 0) {
    throw new Error(
      `Services not healthy after ${timeoutMs}ms:\n` +
        unhealthy
          .map((s) => `  - ${s.name}: ${s.error ?? s.status}`)
          .join('\n')
    );
  }

  return services;
}

/**
 * Wait for core services to be healthy.
 */
export async function waitForCoreServices(
  timeoutMs: number = 60000
): Promise<ServiceHealth[]> {
  return waitForServices(() => checkCoreServices(), timeoutMs);
}

/**
 * Wait for dataspace services to be healthy.
 */
export async function waitForDataspaceServices(
  timeoutMs: number = 120000
): Promise<ServiceHealth[]> {
  return waitForServices(
    () => checkServicesForProfile('dataspace'),
    timeoutMs
  );
}

/**
 * Wait for magic import services to be healthy.
 */
export async function waitForMagicImportServices(
  timeoutMs: number = 60000
): Promise<ServiceHealth[]> {
  return waitForServices(
    () => checkServicesForProfile('magic-import'),
    timeoutMs
  );
}

/**
 * Wait for PLC services to be healthy.
 */
export async function waitForPlcServices(
  timeoutMs: number = 120000
): Promise<ServiceHealth[]> {
  return waitForServices(
    () => checkServicesForProfile('plc'),
    timeoutMs
  );
}

// ============================================================================
// Docker Compose Helpers
// ============================================================================

/**
 * Check if Docker is available.
 */
export async function isDockerAvailable(): Promise<boolean> {
  try {
    await execAsync('docker --version', { timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if Docker Compose is available.
 */
export async function isDockerComposeAvailable(): Promise<boolean> {
  try {
    await execAsync('docker compose version', { timeout: 5000 });
    return true;
  } catch {
    // Try legacy docker-compose
    try {
      await execAsync('docker-compose --version', { timeout: 5000 });
      return true;
    } catch {
      return false;
    }
  }
}

/**
 * Get running Docker Compose services.
 */
export async function getRunningServices(): Promise<string[]> {
  try {
    const { stdout } = await execAsync(
      'docker compose ps --format "{{.Name}}" 2>/dev/null || docker-compose ps --format "{{.Name}}" 2>/dev/null',
      { timeout: 10000 }
    );

    return stdout
      .trim()
      .split('\n')
      .filter((name) => name.length > 0);
  } catch {
    return [];
  }
}
