export function normalizeProviderId(value: unknown): string {
  return String(value ?? '').trim().toLowerCase()
}
