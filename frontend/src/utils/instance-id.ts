/**
 * Identifiers for submodel instances.
 *
 * An instance must not reuse the identifier of the template it was created
 * from, so the editor proposes a fresh one that the user can replace with an
 * identifier from their own namespace.
 */

function randomBytes(length: number): Uint8Array {
  const bytes = new Uint8Array(length);
  const source = globalThis.crypto;
  if (source && typeof source.getRandomValues === 'function') {
    source.getRandomValues(bytes);
  } else {
    for (let index = 0; index < length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  return bytes;
}

/**
 * Random (version 4) UUID.
 *
 * `crypto.randomUUID` only exists in secure contexts, and the editor is also
 * served over plain HTTP inside plant networks, hence the manual fallback.
 */
function randomUuid(): string {
  const source = globalThis.crypto;
  if (source && typeof source.randomUUID === 'function') {
    return source.randomUUID();
  }

  const bytes = randomBytes(16);
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC 9562 variant
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'));
  return [
    hex.slice(0, 4).join(''),
    hex.slice(4, 6).join(''),
    hex.slice(6, 8).join(''),
    hex.slice(8, 10).join(''),
    hex.slice(10, 16).join(''),
  ].join('-');
}

/** A new identifier for a submodel instance, e.g. `urn:uuid:3f2c…`. */
export function newInstanceId(): string {
  return `urn:uuid:${randomUuid()}`;
}
