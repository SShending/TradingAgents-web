import type { AssetMode, Instrument } from './types'

async function json<T>(response: Response): Promise<T> {
  const body = await response.json()
  if (!response.ok) {
    throw new Error(body.detail?.message ?? body.detail ?? 'Request failed')
  }
  return body as T
}

export function resolveInstrument(symbol: string, asset_type: AssetMode) {
  return fetch('/api/instruments/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, asset_type }),
  }).then(json<Instrument>)
}

export function createAnalysis(payload: Record<string, unknown>) {
  return fetch('/api/analyses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(json<{ job_id: string; status: string }>)
}

export function cancelAnalysis(jobId: string) {
  return fetch(`/api/analyses/${jobId}/cancel`, { method: 'POST' }).then(json<{ status: string }>)
}
