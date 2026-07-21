export type AssetMode = 'auto' | 'stock' | 'fund' | 'crypto'
export type JobStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelling' | 'cancelled'

export interface Instrument {
  requested_symbol: string
  canonical_symbol: string
  asset_type: Exclude<AssetMode, 'auto'>
  fund_type?: string | null
  quote_type?: string | null
  name?: string | null
  exchange?: string | null
  currency?: string | null
  warnings: string[]
}

export interface AnalysisEvent {
  id: number
  job_id: string
  type: string
  timestamp: string
  data: Record<string, unknown>
}

export interface Metric {
  name: string
  value: number | null
  unit: string
  window?: string
  reason_if_unavailable?: string
}

export interface Snapshot {
  instrument: Record<string, unknown>
  profile: Record<string, number | string | null>
  metrics: Metric[]
  price_series: Array<{ date: string; adjusted_close: number; benchmark?: number }>
  top_holdings: Array<{ symbol?: string; name?: string; weight?: number }>
  sectors: Record<string, number>
  warnings: string[]
}

export interface AnalysisResult {
  asset_type: string
  company_of_interest: string
  trade_date: string
  benchmark_symbol: string
  fund_snapshot?: Snapshot | null
  [key: string]: unknown
}

export interface AnalysisState {
  status: JobStatus
  jobId?: string
  lastEventId: number
  connected: boolean
  agents: Record<string, string>
  reports: Record<string, string>
  result?: AnalysisResult
  error?: string
}
