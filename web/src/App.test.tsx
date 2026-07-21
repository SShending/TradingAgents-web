import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'

class FakeEventSource {
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  addEventListener() {}
  close() {}
}

beforeEach(() => {
  vi.stubGlobal('EventSource', FakeEventSource)
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/resolve')) return new Response(JSON.stringify({ requested_symbol:'SPY', canonical_symbol:'SPY', asset_type:'fund', fund_type:'etf', quote_type:'ETF', name:'SPDR S&P 500 ETF Trust', exchange:'PCX', currency:'USD', warnings:[] }), { status: 200 })
    return new Response(JSON.stringify({ job_id:'job-1', status:'queued' }), { status: 202 })
  }))
})

afterEach(() => vi.unstubAllGlobals())

it('requires instrument resolution before start and renders resolved fund identity', async () => {
  render(<App />)
  expect(screen.getByRole('button', { name: /start analysis/i })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Resolve' }))
  await waitFor(() => expect(screen.getAllByText('SPDR S&P 500 ETF Trust')).toHaveLength(2))
  expect(screen.getByRole('button', { name: /start analysis/i })).toBeEnabled()
})

it('renders stable empty report states and accessible export action', () => {
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Analyst Reports' }))
  expect(screen.getByText('No report content yet')).toBeInTheDocument()
  expect(screen.getByLabelText('Download Markdown report')).toBeInTheDocument()
})
