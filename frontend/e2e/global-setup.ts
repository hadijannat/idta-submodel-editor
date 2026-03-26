/**
 * Global setup for E2E tests.
 *
 * Runs before all tests to ensure services are ready.
 */

import { FullConfig } from '@playwright/test';
import {
  checkCoreServices,
  waitForCoreServices,
  checkDataspaceServices,
  waitForDataspaceServices,
  checkMagicImportServices,
  waitForMagicImportServices,
  checkPlcServices,
  waitForPlcServices,
  isDockerAvailable,
} from './helpers/docker-health';
import { isConformanceToolAvailable, getConformanceToolVersion } from './helpers/conformance-runner';

// Determine the test profile from environment
type TestProfile = 'default' | 'magic-import' | 'dataspace' | 'plc';

function getTestProfile(): TestProfile {
  const profile = process.env.E2E_PROFILE || 'default';
  if (['default', 'magic-import', 'dataspace', 'plc'].includes(profile)) {
    return profile as TestProfile;
  }
  return 'default';
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const profile = getTestProfile();
  const timeout = parseInt(process.env.E2E_SETUP_TIMEOUT || '120000', 10);
  const profileServiceTimeout = Math.min(timeout, 20000);

  console.log(`\n🚀 E2E Test Setup (profile: ${profile})`);
  console.log('━'.repeat(50));

  // Check Docker availability
  const dockerAvailable = await isDockerAvailable();
  if (!dockerAvailable) {
    console.log('⚠️  Docker is not available. Some health checks may fail.');
  }

  // Check conformance tool availability
  const conformanceAvailable = await isConformanceToolAvailable();
  if (conformanceAvailable) {
    const version = await getConformanceToolVersion();
    console.log(`✓ Conformance tool available${version ? `: ${version}` : ''}`);
  } else {
    console.log(
      '⚠️  aas-test-engines not available. Conformance tests will be skipped.'
    );
    console.log('   Install with: pip install aas-test-engines');
  }

  // Store conformance availability for tests
  process.env.CONFORMANCE_TOOL_AVAILABLE = conformanceAvailable ? 'true' : 'false';

  // Wait for services based on profile
  try {
    console.log('\n📡 Checking service health...\n');

    switch (profile) {
      case 'magic-import':
        await waitForMagicImportServices(timeout);
        break;
      case 'dataspace':
        await waitForCoreServices(timeout);
        try {
          await waitForDataspaceServices(profileServiceTimeout);
        } catch (dataspaceError) {
          process.env.E2E_DATASPACE_MOCK_ONLY = 'true';
          console.warn(
            `⚠️  Dataspace services unavailable, proceeding in mock-only mode: ${
              dataspaceError instanceof Error ? dataspaceError.message : String(dataspaceError)
            }`
          );
        }
        break;
      case 'plc':
        await waitForCoreServices(timeout);
        try {
          await waitForPlcServices(profileServiceTimeout);
        } catch (plcError) {
          process.env.E2E_PLC_MOCK_ONLY = 'true';
          process.env.E2E_DATASPACE_MOCK_ONLY = 'true';
          console.warn(
            `⚠️  PLC/dataspace services unavailable, proceeding in mock-only mode: ${
              plcError instanceof Error ? plcError.message : String(plcError)
            }`
          );
        }
        break;
      default:
        await waitForCoreServices(timeout);
    }

    // Print service status
    await printServiceStatus(profile);

    console.log('\n✅ All required services are healthy\n');
  } catch (error) {
    console.error('\n❌ Service health check failed:\n');

    // Print detailed status for debugging
    await printServiceStatus(profile);

    // Re-throw to fail the test run
    throw error;
  }

  // Print test configuration summary
  console.log('📋 Test Configuration');
  console.log('━'.repeat(50));
  console.log(`   Base URL: ${process.env.DEMO_BASE_URL || 'http://localhost:8080'}`);
  console.log(`   API URL: ${process.env.VITE_API_URL || 'http://localhost:8000'}`);
  console.log(`   Profile: ${profile}`);
  console.log(`   Headless: ${process.env.PW_HEADLESS !== 'false'}`);
  console.log(`   Workers: ${config.workers}`);
  console.log('');
}

async function printServiceStatus(profile: TestProfile): Promise<void> {
  const services = [];

  // Always check core services
  services.push(...(await checkCoreServices({ timeout: 3000 })));

  // Profile-specific services
  switch (profile) {
    case 'magic-import':
      services.push(...(await checkMagicImportServices({ timeout: 3000 })));
      break;
    case 'dataspace':
      services.push(...(await checkDataspaceServices({ timeout: 3000 })));
      break;
    case 'plc':
      services.push(...(await checkDataspaceServices({ timeout: 3000 })));
      services.push(...(await checkPlcServices({ timeout: 3000 })));
      break;
  }

  // Print status table
  const maxNameLength = Math.max(...services.map((s) => s.name.length));

  for (const service of services) {
    const icon = service.status === 'healthy' ? '✓' : '✗';
    const color = service.status === 'healthy' ? '\x1b[32m' : '\x1b[31m';
    const reset = '\x1b[0m';
    const name = service.name.padEnd(maxNameLength);
    const latency = service.latency_ms ? `(${service.latency_ms}ms)` : '';
    const error = service.error ? ` - ${service.error}` : '';

    console.log(`   ${color}${icon}${reset} ${name} ${latency}${error}`);
  }
}
