/** 生成幂等键所需的 UUID v4（优先使用 crypto.randomUUID）。 */
export function uuidV4(): string {
  const g = globalThis as unknown as { crypto?: Crypto };
  if (g.crypto?.randomUUID) {
    return g.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  (g.crypto as Crypto).getRandomValues(bytes);
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40;
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** 生成 `request_key` 业务去重键。 */
export function requestKey(prefix = 'web'): string {
  return `${prefix}-${uuidV4()}`;
}
