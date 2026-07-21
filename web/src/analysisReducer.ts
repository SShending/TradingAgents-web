import type { AnalysisEvent, AnalysisState } from './types'

export const initialAnalysisState: AnalysisState = {
  status: 'idle',
  lastEventId: 0,
  connected: false,
  agents: {},
  reports: {},
}

export type Action =
  | { type: 'created'; jobId: string }
  | { type: 'connected'; value: boolean }
  | { type: 'event'; event: AnalysisEvent }
  | { type: 'reset' }
  | { type: 'error'; message: string }
  | { type: 'cancelling' }

export function analysisReducer(state: AnalysisState, action: Action): AnalysisState {
  if (action.type === 'reset') return initialAnalysisState
  if (action.type === 'created') return { ...initialAnalysisState, status: 'queued', jobId: action.jobId }
  if (action.type === 'connected') return { ...state, connected: action.value }
  if (action.type === 'error') return { ...state, status: 'failed', error: action.message }
  if (action.type === 'cancelling') return { ...state, status: 'cancelling' }
  const event = action.event
  if (event.id <= state.lastEventId) return state
  const next = { ...state, lastEventId: event.id }
  const agent = String(event.data.agent ?? '')
  if (event.type === 'analysis.started') next.status = 'running'
  if (event.type === 'agent.started') next.agents = { ...state.agents, [agent]: 'running' }
  if (event.type === 'agent.completed') next.agents = { ...state.agents, [agent]: 'completed' }
  if (event.type === 'agent.skipped') next.agents = { ...state.agents, [agent]: 'skipped' }
  if (event.type === 'report.updated') {
    next.reports = { ...state.reports, [String(event.data.section)]: String(event.data.content ?? '') }
  }
  if (event.type === 'analysis.completed') {
    next.status = 'completed'
    next.result = event.data.result as AnalysisState['result']
    next.connected = false
  }
  if (event.type === 'analysis.failed') {
    next.status = 'failed'
    next.error = String(event.data.message ?? 'Analysis failed')
    next.connected = false
  }
  if (event.type === 'analysis.cancelled') {
    next.status = 'cancelled'
    next.connected = false
  }
  return next
}
