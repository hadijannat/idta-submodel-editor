import { afterEach, describe, expect, it, vi } from 'vitest';
import { newInstanceId } from '../instance-id';

const UUID_V4 =
  /^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('newInstanceId', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns a urn:uuid identifier', () => {
    expect(newInstanceId()).toMatch(UUID_V4);
  });

  it('returns a different identifier each time', () => {
    const ids = new Set(Array.from({ length: 50 }, () => newInstanceId()));
    expect(ids.size).toBe(50);
  });

  it('works without crypto.randomUUID (plain HTTP pages)', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.fill(0xff);
        return bytes;
      },
    });

    expect(newInstanceId()).toBe('urn:uuid:ffffffff-ffff-4fff-bfff-ffffffffffff');
  });

  it('works without any crypto support', () => {
    vi.stubGlobal('crypto', undefined);

    expect(newInstanceId()).toMatch(UUID_V4);
  });
});
