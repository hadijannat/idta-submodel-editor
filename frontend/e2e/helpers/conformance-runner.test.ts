import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildConformanceArgs,
  getConformanceToolVersion,
  isConformanceToolAvailable,
  parseConformanceOutput,
  runConformanceCheck,
  setExecFileImplementationForTests,
} from './conformance-runner';

const execFileMock = vi.fn();

function mockExecFileSuccess(stdout = '', stderr = ''): void {
  execFileMock.mockImplementation((_file, _args, _options, callback) => {
    callback(null, stdout, stderr);
  });
}

function mockExecFileFailure(message: string, stdout = '', stderr = ''): void {
  execFileMock.mockImplementation((_file, _args, _options, callback) => {
    const error = Object.assign(new Error(message), { stdout, stderr });
    callback(error, stdout, stderr);
  });
}

describe('conformance runner helpers', () => {
  beforeEach(() => {
    execFileMock.mockReset();
    setExecFileImplementationForTests(execFileMock as unknown as typeof import('child_process').execFile);
  });

  afterEach(() => {
    setExecFileImplementationForTests(null);
  });

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

  it('checks conformance tool availability with the supported help command', async () => {
    mockExecFileSuccess();

    await expect(isConformanceToolAvailable()).resolves.toBe(true);
    expect(execFileMock).toHaveBeenCalledWith(
      'aas_test_engines',
      ['check_file', '--help'],
      { timeout: 5000 },
      expect.any(Function)
    );
  });

  it('returns false when the conformance tool probe fails', async () => {
    mockExecFileFailure('missing tool');

    await expect(isConformanceToolAvailable()).resolves.toBe(false);
  });

  it('falls back from python3 to python when reading the conformance tool version', async () => {
    execFileMock
      .mockImplementationOnce((_file, _args, _options, callback) => {
        callback(new Error('python3 missing'), '', '');
      })
      .mockImplementationOnce((_file, _args, _options, callback) => {
        callback(null, '1.0.3\n', '');
      });

    await expect(getConformanceToolVersion()).resolves.toBe('aas-test-engines 1.0.3');
    expect(execFileMock).toHaveBeenNthCalledWith(
      1,
      'python3',
      ['-c', "from importlib import metadata; print(metadata.version('aas-test-engines'))"],
      { timeout: 5000 },
      expect.any(Function)
    );
    expect(execFileMock).toHaveBeenNthCalledWith(
      2,
      'python',
      ['-c', "from importlib import metadata; print(metadata.version('aas-test-engines'))"],
      { timeout: 5000 },
      expect.any(Function)
    );
  });

  it('returns null when no Python interpreter can report the conformance package version', async () => {
    execFileMock
      .mockImplementationOnce((_file, _args, _options, callback) => {
        callback(new Error('python3 missing'), '', '');
      })
      .mockImplementationOnce((_file, _args, _options, callback) => {
        callback(new Error('python missing'), '', '');
      });

    await expect(getConformanceToolVersion()).resolves.toBeNull();
  });

  it('runs conformance checks with execFile and the supported argument list', async () => {
    mockExecFileSuccess('{"m":"Check","l":0,"s":[]}', '');

    const result = await runConformanceCheck(Buffer.from('PK\x03\x04dummy'), {
      format: 'aasx',
    });

    expect(execFileMock).toHaveBeenCalledWith(
      'aas_test_engines',
      ['check_file', '--format', 'aasx', '--output', 'json', expect.stringMatching(/test\.aasx$/)],
      { timeout: 30000 },
      expect.any(Function)
    );
    expect(result.passed).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('returns a failing result when the subprocess rejects without structured output', async () => {
    mockExecFileFailure('spawn failed');

    const result = await runConformanceCheck('{}', {
      format: 'json',
    });

    expect(result.passed).toBe(false);
    expect(result.errors).toEqual([
      {
        level: 'error',
        message: 'Conformance check failed: spawn failed',
      },
    ]);
  });
});
