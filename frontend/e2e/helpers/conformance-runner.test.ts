import { describe, expect, it } from 'vitest';

import {
  buildConformanceArgs,
  getConformanceToolVersion,
  isConformanceToolAvailable,
  parseConformanceOutput,
} from './conformance-runner';

type ExecRunner = NonNullable<Parameters<typeof isConformanceToolAvailable>[0]>;

describe('conformance runner environment detection', () => {
  it('detects the conformance CLI when check_file help succeeds', async () => {
    const calls: Parameters<ExecRunner>[] = [];
    const execRunner: ExecRunner = async (...args) => {
      calls.push(args);
      return { stdout: '', stderr: '' };
    };

    await expect(isConformanceToolAvailable(execRunner)).resolves.toBe(true);
    expect(calls).toEqual([[
      'aas_test_engines',
      ['check_file', '--help'],
      { timeout: 5000 },
    ]]);
  });

  it('falls back from python3 to python when resolving the version', async () => {
    const calls: Parameters<ExecRunner>[] = [];
    let invocation = 0;
    const execRunner: ExecRunner = async (...args) => {
      calls.push(args);
      invocation += 1;
      if (invocation === 1) {
        throw Object.assign(new Error('python3 missing'), { code: 'ENOENT' });
      }
      return { stdout: '1.2.3\n', stderr: '' };
    };

    await expect(getConformanceToolVersion(execRunner)).resolves.toBe('aas-test-engines 1.2.3');
    expect(calls).toEqual([
      [
        'python3',
        ['-c', "from importlib import metadata; print(metadata.version('aas-test-engines'))"],
        { timeout: 5000 },
      ],
      [
        'python',
        ['-c', "from importlib import metadata; print(metadata.version('aas-test-engines'))"],
        { timeout: 5000 },
      ],
    ]);
  });

  it('keeps availability true when version lookup is unavailable', async () => {
    const availabilityRunner: ExecRunner = async () => ({ stdout: '', stderr: '' });
    const versionCalls: Parameters<ExecRunner>[] = [];
    const versionRunner: ExecRunner = async (...args) => {
      versionCalls.push(args);
      throw Object.assign(new Error('metadata unavailable'), { code: 'ENOENT' });
    };

    await expect(isConformanceToolAvailable(availabilityRunner)).resolves.toBe(true);
    await expect(getConformanceToolVersion(versionRunner)).resolves.toBeNull();
    expect(versionCalls).toEqual([
      [
        'python3',
        ['-c', "from importlib import metadata; print(metadata.version('aas-test-engines'))"],
        { timeout: 5000 },
      ],
      [
        'python',
        ['-c', "from importlib import metadata; print(metadata.version('aas-test-engines'))"],
        { timeout: 5000 },
      ],
    ]);
  });
});

describe('conformance runner helpers', () => {
  it('uses the supported aas-test-engines CLI arguments', () => {
    const args = buildConformanceArgs('/tmp/example.aasx', {
      format: 'aasx',
      version: 'v3.0',
      rules: ['strict'],
    });

    expect(args).toEqual([
      'check_file',
      '--format',
      'aasx',
      '--output',
      'json',
      '/tmp/example.aasx',
    ]);
  });

  it('parses aas-test-engines JSON tree output into flat issues', () => {
    const output = JSON.stringify({
      m: 'Check',
      l: 2,
      s: [
        {
          m: 'Check meta model',
          l: 2,
          s: [{ m: 'Unknown additional attribute foo @ /', l: 2, s: [] }],
        },
        { m: 'Skipped checking of constraints', l: 1, s: [] },
      ],
    });

    const result = parseConformanceOutput(output, '');

    expect(result.passed).toBe(false);
    expect(result.errors).toEqual([
      {
        level: 'error',
        message: 'Unknown additional attribute foo @ /',
      },
    ]);
    expect(result.warnings).toEqual([
      {
        level: 'warning',
        message: 'Skipped checking of constraints',
      },
    ]);
  });

  it('falls back to parsing plain-text output when JSON is unavailable', () => {
    const result = parseConformanceOutput(
      'FAILED check meta model\nWARNING minor issue',
      ''
    );

    expect(result.passed).toBe(false);
    expect(result.errors).toEqual([
      {
        level: 'error',
        message: 'FAILED check meta model',
      },
    ]);
    expect(result.warnings).toEqual([
      {
        level: 'warning',
        message: 'WARNING minor issue',
      },
    ]);
  });

  it('extracts JSON output even when the CLI prints a preamble', () => {
    const result = parseConformanceOutput(
      'Running conformance check...\n{"m":"Check","l":2,"s":[{"m":"invalid shell","l":2,"s":[]}]}',
      ''
    );

    expect(result.passed).toBe(false);
    expect(result.errors).toEqual([
      {
        level: 'error',
        message: 'invalid shell',
      },
    ]);
  });
});
