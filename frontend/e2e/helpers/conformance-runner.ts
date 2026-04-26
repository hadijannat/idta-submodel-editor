/**
 * Conformance validation runner using aas-test-engines.
 *
 * Wraps the aas-test-engines CLI tool to validate exported AASX/JSON
 * files against the official AAS specification.
 *
 * Requires: pip install aas-test-engines
 */

import { execFile } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

const CONFORMANCE_BINARY = 'aas_test_engines';
const PYTHON_BINARIES = ['python3', 'python'];
const CONFORMANCE_VERSION_SNIPPET =
  "from importlib import metadata; print(metadata.version('aas-test-engines'))";

// ============================================================================
// Types
// ============================================================================

export interface ConformanceResult {
  passed: boolean;
  score?: number;
  errors: ConformanceIssue[];
  warnings: ConformanceIssue[];
  stdout: string;
  stderr: string;
  duration_ms: number;
}

export interface ConformanceIssue {
  level: 'error' | 'warning';
  rule?: string;
  path?: string;
  message: string;
}

export interface ConformanceOptions {
  /**
   * Format of the input file.
   */
  format: 'aasx' | 'json';

  /**
   * Timeout in milliseconds.
   * @default 30000
   */
  timeout?: number;

  /**
   * Retained for API compatibility. aas-test-engines 1.x does not expose a
   * validation-version flag for `check_file`, so this value is currently unused.
   */
  version?: string;

  /**
   * Retained for API compatibility. aas-test-engines 1.x does not expose a
   * rule-selection flag for `check_file`, so this value is currently unused.
   */
  rules?: string[];
}

interface ConformanceTreeNode {
  m?: string;
  l?: number;
  s?: ConformanceTreeNode[];
}

interface ExecFileResult {
  stdout: string;
  stderr: string;
}

type ExecFileImplementation = typeof execFile;
type ExecFileError = Error & {
  stdout?: string;
  stderr?: string;
};

let execFileImplementation: ExecFileImplementation = execFile;

export function setExecFileImplementationForTests(
  implementation: ExecFileImplementation | null
): void {
  execFileImplementation = implementation ?? execFile;
}

function execFileAsync(file: string, args: string[], timeout: number): Promise<ExecFileResult> {
  return new Promise((resolve, reject) => {
    execFileImplementation(file, args, { timeout }, (error, stdout, stderr) => {
      const stdoutText = String(stdout ?? '');
      const stderrText = String(stderr ?? '');

      if (error) {
        const execError = error as ExecFileError;
        execError.stdout = stdoutText;
        execError.stderr = stderrText;
        reject(execError);
        return;
      }

      resolve({
        stdout: stdoutText,
        stderr: stderrText,
      });
    });
  });
}

// ============================================================================
// Conformance Runner
// ============================================================================

/**
 * Run conformance check on an AASX or JSON file.
 *
 * @param content - File content as Buffer (AASX) or string (JSON)
 * @param options - Validation options
 * @returns Conformance result with pass/fail status and issues
 */
export async function runConformanceCheck(
  content: Buffer | string,
  options: ConformanceOptions
): Promise<ConformanceResult> {
  const startTime = Date.now();

  // Create temp file
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aas-conformance-'));
  const extension = options.format === 'aasx' ? '.aasx' : '.json';
  const tempFile = path.join(tempDir, `test${extension}`);

  try {
    // Write content to temp file
    if (Buffer.isBuffer(content)) {
      fs.writeFileSync(tempFile, content);
    } else {
      fs.writeFileSync(tempFile, content, 'utf-8');
    }

    // Build command
    const args = buildConformanceArgs(tempFile, options);

    // Execute
    const timeout = options.timeout ?? 30000;
    const { stdout, stderr } = await execFileAsync(CONFORMANCE_BINARY, args, timeout);

    // Parse result
    const result = parseConformanceOutput(stdout, stderr);
    result.duration_ms = Date.now() - startTime;

    return result;
  } catch (error: unknown) {
    // Handle execution errors
    const execError = error as { stdout?: string; stderr?: string; code?: number; message?: string };
    const stdout = execError.stdout ?? '';
    const stderr = execError.stderr ?? '';

    // Try to parse output even on failure
    const result = parseConformanceOutput(stdout, stderr);
    result.duration_ms = Date.now() - startTime;

    // If we couldn't parse meaningful output, add the error
    if (result.errors.length === 0 && execError.message) {
      result.passed = false;
      result.errors.push({
        level: 'error',
        message: `Conformance check failed: ${execError.message}`,
      });
    }

    return result;
  } finally {
    // Cleanup temp files
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch {
      // Ignore cleanup errors
    }
  }
}

/**
 * Build the aas-test-engines command arguments.
 *
 * Exported for unit tests.
 */
export function buildConformanceArgs(filePath: string, options: ConformanceOptions): string[] {
  const args = ['check_file'];

  // Format
  args.push('--format', options.format);

  // aas-test-engines 1.x supports --output, but not --output-format / --version / --rule.
  args.push('--output', 'json');

  // File path
  args.push(filePath);

  return args;
}

/**
 * Parse aas-test-engines' JSON tree into flat issues.
 */
function collectTreeIssues(node: ConformanceTreeNode, result: ConformanceResult): void {
  const children = Array.isArray(node.s) ? node.s : [];
  if (children.length > 0) {
    for (const child of children) {
      collectTreeIssues(child, result);
    }
    return;
  }

  const message = typeof node.m === 'string' ? node.m.trim() : '';
  if (!message) {
    return;
  }

  if ((node.l ?? 0) >= 2) {
    result.passed = false;
    result.errors.push({
      level: 'error',
      message,
    });
    return;
  }

  if ((node.l ?? 0) === 1) {
    result.warnings.push({
      level: 'warning',
      message,
    });
  }
}

/**
 * Parse the conformance tool output.
 *
 * Exported for unit tests.
 */
export function parseConformanceOutput(stdout: string, stderr: string): ConformanceResult {
  const result: ConformanceResult = {
    passed: true,
    errors: [],
    warnings: [],
    stdout,
    stderr,
    duration_ms: 0,
  };

  // Try to parse JSON output even if the CLI prints a short preamble first.
  const jsonMatch = stdout.match(/\{[\s\S]*\}/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[0]) as ConformanceTreeNode;
      collectTreeIssues(parsed, result);
      result.passed = result.errors.length === 0;
      return result;
    } catch {
      // Fall through to line-based parsing when JSON is malformed.
    }
  }

  // Fall back to line-by-line parsing
  const lines = (stdout + '\n' + stderr).split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    const normalized = trimmed.toLowerCase();
    const isError =
      /\b(error|failed|invalid)\b/i.test(trimmed) || normalized.includes('[error]');
    const isWarning = /\bwarning\b/i.test(trimmed) || normalized.includes('[warning]');

    if (!trimmed) {
      continue;
    }

    if (isError) {
      result.passed = false;
      result.errors.push({
        level: 'error',
        message: trimmed,
      });
    } else if (isWarning) {
      result.warnings.push({
        level: 'warning',
        message: trimmed,
      });
    } else if (normalized.includes('passed') || normalized.includes('valid')) {
      // Keep passed as true
    }
  }

  return result;
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Check if aas-test-engines is installed and available.
 */
export async function isConformanceToolAvailable(): Promise<boolean> {
  try {
    await execFileAsync(CONFORMANCE_BINARY, ['check_file', '--help'], 5000);
    return true;
  } catch {
    return false;
  }
}

/**
 * Get the version of aas-test-engines.
 */
export async function getConformanceToolVersion(): Promise<string | null> {
  for (const pythonBinary of PYTHON_BINARIES) {
    try {
      const { stdout } = await execFileAsync(
        pythonBinary,
        ['-c', CONFORMANCE_VERSION_SNIPPET],
        5000
      );
      const version = stdout.trim();
      if (version) {
        return `aas-test-engines ${version}`;
      }
    } catch {
      continue;
    }
  }

  return null;
}

/**
 * Validate AASX content.
 */
export async function validateAasx(
  content: Buffer,
  options?: Omit<ConformanceOptions, 'format'>
): Promise<ConformanceResult> {
  return runConformanceCheck(content, { ...options, format: 'aasx' });
}

/**
 * Validate JSON content.
 */
export async function validateJson(
  content: string | object,
  options?: Omit<ConformanceOptions, 'format'>
): Promise<ConformanceResult> {
  const jsonString = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
  return runConformanceCheck(jsonString, { ...options, format: 'json' });
}

// ============================================================================
// Assertions
// ============================================================================

/**
 * Assert that content passes conformance check.
 * Throws an error with detailed information if validation fails.
 */
export async function assertConformancePass(
  content: Buffer | string,
  options: ConformanceOptions
): Promise<ConformanceResult> {
  const result = await runConformanceCheck(content, options);

  if (!result.passed) {
    const errorDetails = result.errors
      .map((e) => `  - ${e.message}${e.path ? ` (at ${e.path})` : ''}`)
      .join('\n');

    throw new Error(
      `Conformance check failed with ${result.errors.length} error(s):\n${errorDetails}`
    );
  }

  return result;
}

/**
 * Assert that AASX passes conformance check.
 */
export async function assertAasxConformance(
  content: Buffer,
  options?: Omit<ConformanceOptions, 'format'>
): Promise<ConformanceResult> {
  return assertConformancePass(content, { ...options, format: 'aasx' });
}

/**
 * Assert that JSON passes conformance check.
 */
export async function assertJsonConformance(
  content: string | object,
  options?: Omit<ConformanceOptions, 'format'>
): Promise<ConformanceResult> {
  const jsonString = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
  return assertConformancePass(jsonString, { ...options, format: 'json' });
}
