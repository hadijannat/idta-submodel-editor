import { describe, expect, it } from 'vitest';

import { buildConformanceArgs, parseConformanceOutput } from './conformance-runner';

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
