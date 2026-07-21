import { useEffect, useMemo, useReducer, useState } from 'react'
import { AlertTriangle, Check, Download, Menu, Play, RotateCcw, Square, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { cancelAnalysis, createAnalysis, resolveInstrument } from './api'
import { analysisReducer, initialAnalysisState } from './analysisReducer'
import type { AnalysisEvent, AssetMode, Instrument, Metric, Snapshot } from './types'

const analysts = [
  ['market', 'Market'], ['social', 'Sentiment'], ['news', 'News'], ['fundamentals', 'Fundamentals'],
]
const agentOrder = ['Market Analyst', 'Sentiment Analyst', 'News Analyst', 'Fundamentals Analyst']
const tabs = ['Overview', 'Analyst Reports', 'Debate & Risk', 'Final Decision']
const eventTypes = ['analysis.started', 'agent.started', 'agent.completed', 'agent.skipped', 'report.updated', 'analysis.completed', 'analysis.failed', 'analysis.cancelled']

function today() { return new Date().toISOString().slice(0, 10) }
function pct(value: number | null | undefined) { return value == null ? 'N/A' : `${(value * 100).toFixed(1)}%` }
function metricLabel(metric: Metric) {
  const labels: Record<string, string> = { total_return: 'Total return', annualized_volatility: 'Volatility', maximum_drawdown: 'Max drawdown', tracking_error: 'Tracking error' }
  return `${labels[metric.name] ?? metric.name}${metric.window ? ` · ${metric.window}` : ''}`
}

export default function App() {
  const [mode, setMode] = useState<AssetMode>('auto')
  const [symbol, setSymbol] = useState('SPY')
  const [date, setDate] = useState(today())
  const [benchmark, setBenchmark] = useState('SPY')
  const [selected, setSelected] = useState(['market', 'social', 'news', 'fundamentals'])
  const [instrument, setInstrument] = useState<Instrument>()
  const [resolveError, setResolveError] = useState('')
  const [resolving, setResolving] = useState(false)
  const [tab, setTab] = useState(tabs[0])
  const [drawer, setDrawer] = useState(false)
  const [state, dispatch] = useReducer(analysisReducer, initialAnalysisState)

  const active = ['queued', 'running', 'cancelling'].includes(state.status)
  const snapshot = state.result?.fund_snapshot

  useEffect(() => {
    if (!state.jobId || !['queued', 'running', 'cancelling'].includes(state.status)) return
    const source = new EventSource(`/api/analyses/${state.jobId}/events`)
    source.onopen = () => dispatch({ type: 'connected', value: true })
    source.onerror = () => {
      dispatch({ type: 'connected', value: false })
      if (!['completed', 'failed', 'cancelled'].includes(state.status)) source.close()
    }
    for (const type of eventTypes) {
      source.addEventListener(type, (raw) => dispatch({ type: 'event', event: JSON.parse((raw as MessageEvent).data) as AnalysisEvent }))
    }
    return () => source.close()
  }, [state.jobId, state.status])

  async function resolve() {
    setResolving(true); setResolveError('')
    try { setInstrument(await resolveInstrument(symbol, mode)) }
    catch (error) { setInstrument(undefined); setResolveError(error instanceof Error ? error.message : 'Unable to resolve symbol') }
    finally { setResolving(false) }
  }

  async function start() {
    if (!instrument) return
    try {
      const job = await createAnalysis({ symbol: instrument.canonical_symbol, asset_type: mode, analysis_date: date, benchmark_symbol: benchmark, analysts: selected, research_depth: 1, llm_provider: 'openai', quick_model: 'gpt-5.4-mini', deep_model: 'gpt-5.5', output_language: 'English' })
      dispatch({ type: 'created', jobId: job.job_id }); setDrawer(false)
    } catch (error) { dispatch({ type: 'error', message: error instanceof Error ? error.message : 'Unable to start analysis' }) }
  }

  async function cancel() {
    if (!state.jobId) return
    dispatch({ type: 'cancelling' })
    try { await cancelAnalysis(state.jobId) } catch (error) { dispatch({ type: 'error', message: error instanceof Error ? error.message : 'Cancellation failed' }) }
  }

  const reports = useMemo(() => Object.entries(state.reports), [state.reports])
  return <div className="app-shell">
    <header className="topbar">
      <button className="icon-button menu-button" aria-label="Open configuration" title="Configuration" onClick={() => setDrawer(true)}><Menu size={19}/></button>
      <div className="brand"><span className="brand-mark">TA</span><strong>TradingAgents</strong><span className="edition">Research Workspace</span></div>
      <div className="instrument-title">
        <strong>{instrument?.canonical_symbol ?? 'No instrument'}</strong>
        <span>{instrument?.name ?? 'Resolve a symbol to begin'}</span>
      </div>
      <div className={`connection ${state.connected ? 'online' : ''}`}><span/>{state.connected ? 'Live' : state.status}</div>
    </header>

    <div className="workspace">
      {drawer && <button className="drawer-backdrop" aria-label="Close configuration" onClick={() => setDrawer(false)}/>}
      <aside className={`sidebar ${drawer ? 'open' : ''}`} aria-label="Analysis configuration">
        <div className="sidebar-heading"><div><span className="eyebrow">Configuration</span><h2>Analysis setup</h2></div><button className="icon-button drawer-close" aria-label="Close configuration" onClick={() => setDrawer(false)}><X size={18}/></button></div>
        <label className="field-label">Asset mode</label>
        <div className="segmented" role="group" aria-label="Asset mode">{(['auto','stock','fund','crypto'] as AssetMode[]).map(value => <button key={value} className={mode === value ? 'active' : ''} onClick={() => { setMode(value); setInstrument(undefined) }}>{value}</button>)}</div>
        <label className="field-label" htmlFor="symbol">Symbol</label>
        <div className="resolve-row"><input id="symbol" value={symbol} onChange={event => { setSymbol(event.target.value.toUpperCase()); setInstrument(undefined) }} onKeyDown={event => event.key === 'Enter' && resolve()} /><button className="secondary-button" onClick={resolve} disabled={resolving}>{resolving ? 'Resolving' : 'Resolve'}</button></div>
        {resolveError && <p className="inline-error">{resolveError}</p>}
        {instrument && <div className="identity-block"><div><strong>{instrument.canonical_symbol}</strong><span>{instrument.asset_type}{instrument.fund_type ? ` · ${instrument.fund_type.replace('_',' ')}` : ''}</span></div><Check size={17}/><p>{instrument.name}</p><small>{[instrument.exchange, instrument.currency, instrument.quote_type].filter(Boolean).join(' · ')}</small></div>}
        <div className="field-grid"><label><span className="field-label">Analysis date</span><input type="date" value={date} max={today()} onChange={event => setDate(event.target.value)}/></label><label><span className="field-label">Benchmark</span><input value={benchmark} onChange={event => setBenchmark(event.target.value.toUpperCase())}/></label></div>
        <fieldset><legend>Analysts</legend>{analysts.map(([value,label]) => <label className="check-row" key={value}><input type="checkbox" checked={selected.includes(value)} onChange={() => setSelected(items => items.includes(value) ? items.filter(item => item !== value) : [...items, value])}/><span>{label}</span></label>)}</fieldset>
        <div className="field-grid"><label><span className="field-label">Provider</span><select defaultValue="openai"><option>openai</option><option>ollama</option></select></label><label><span className="field-label">Depth</span><select defaultValue="1"><option value="1">Quick</option><option value="3">Standard</option><option value="5">Deep</option></select></label></div>
        <label><span className="field-label">Output language</span><select defaultValue="English"><option>English</option><option>Chinese</option><option>Spanish</option></select></label>
        <div className="sidebar-actions">{active ? <button className="danger-button" onClick={cancel}><Square size={16}/>Cancel analysis</button> : <button className="primary-button" onClick={start} disabled={!instrument || selected.length === 0}><Play size={17}/>Start analysis</button>}</div>
      </aside>

      <main className="main-content">
        <section className="summary-band">
          <div><span>Instrument</span><strong>{instrument?.canonical_symbol ?? '—'}</strong><small>{instrument?.asset_type ?? 'Not resolved'}</small></div>
          <div><span>Analysis date</span><strong>{date}</strong><small>Price cutoff</small></div>
          <div><span>Benchmark</span><strong>{benchmark}</strong><small>User selected</small></div>
          <div><span>Job</span><strong className="capitalize">{state.status}</strong><small>{state.jobId ? state.jobId.slice(0,8) : 'Not started'}</small></div>
        </section>

        {(resolveError || state.error) && <section className="notice error-notice"><AlertTriangle size={19}/><div><strong>Analysis unavailable</strong><p>{state.error ?? resolveError}</p></div><button className="icon-button" aria-label="Reset error" title="Reset" onClick={() => dispatch({ type:'reset' })}><RotateCcw size={17}/></button></section>}
        {instrument?.warnings.map(warning => <section className="notice" key={warning}><AlertTriangle size={18}/><p>{warning}</p></section>)}

        <section className="progress-strip" aria-label="Agent progress">{agentOrder.map(agent => { const status = state.agents[agent] ?? (active ? 'pending' : 'idle'); return <div key={agent} className={`agent-step ${status}`}><span>{status === 'completed' ? <Check size={14}/> : ''}</span><div><strong>{agent.replace(' Analyst','')}</strong><small>{status}</small></div></div> })}</section>

        <nav className="tabs" aria-label="Report views">{tabs.map(name => <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>)}<a className={`export-button ${state.status !== 'completed' ? 'disabled' : ''}`} aria-label="Download Markdown report" title="Download report" href={state.jobId ? `/api/analyses/${state.jobId}/report.md` : undefined}><Download size={17}/><span>Export</span></a></nav>

        <section className="report-view">
          {tab === 'Overview' && <Overview snapshot={snapshot} instrument={instrument} status={state.status}/>}
          {tab === 'Analyst Reports' && <ReportList reports={reports.filter(([key]) => key.endsWith('_report'))}/>}
          {tab === 'Debate & Risk' && <ReportList reports={reports.filter(([key]) => ['investment_plan','trader_investment_plan'].includes(key))}/>}
          {tab === 'Final Decision' && <ReportList reports={reports.filter(([key]) => key === 'final_trade_decision')}/>}
        </section>
      </main>
    </div>
  </div>
}

function Overview({ snapshot, instrument, status }: { snapshot?: Snapshot | null; instrument?: Instrument; status: string }) {
  if (!snapshot) return <div className="empty-state"><div className="empty-chart"/><h2>{status === 'running' ? 'Analysis in progress' : 'No analysis results yet'}</h2><p>{instrument ? 'Start the analysis to populate metrics, charts, and holdings.' : 'Resolve an instrument from the configuration panel.'}</p></div>
  const metrics = snapshot.metrics ?? []
  const drawdown = snapshot.price_series.map((point) => ({ ...point, drawdown: point.adjusted_close / Math.max(...snapshot.price_series.filter(item => item.date <= point.date).map(item => item.adjusted_close)) - 1 }))
  return <div className="overview-grid">
    <section className="metrics-grid">{metrics.slice(0,5).map((metric) => <div className="metric" key={`${metric.name}-${metric.window}`}><span>{metricLabel(metric)}</span><strong>{metric.value == null ? 'N/A' : metric.unit === 'percent' ? pct(metric.value) : metric.value.toFixed(2)}</strong><small>{metric.reason_if_unavailable ?? 'As of analysis date'}</small></div>)}</section>
    {snapshot.warnings?.map(warning => <section className="notice" key={warning}><AlertTriangle size={18}/><p>{warning}</p></section>)}
    <section className="chart-panel"><header><div><span className="eyebrow">Performance</span><h2>Adjusted price vs benchmark</h2></div><span className="legend"><i/>Fund <i/>Benchmark</span></header><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={snapshot.price_series}><CartesianGrid stroke="#e5e9e7" vertical={false}/><XAxis dataKey="date" tick={{fontSize:11}}/><YAxis tick={{fontSize:11}} width={44}/><Tooltip/><Area isAnimationActive={false} type="monotone" dataKey="adjusted_close" stroke="#156b52" fill="#dbece5" strokeWidth={2}/><Line isAnimationActive={false} type="monotone" dataKey="benchmark" stroke="#c45b31" strokeWidth={2} dot={false}/></AreaChart></ResponsiveContainer></div></section>
    <section className="chart-panel"><header><div><span className="eyebrow">Risk</span><h2>Drawdown</h2></div></header><div className="chart-wrap compact"><ResponsiveContainer width="100%" height="100%"><AreaChart data={drawdown}><CartesianGrid stroke="#e5e9e7" vertical={false}/><XAxis dataKey="date" tick={{fontSize:11}}/><YAxis tickFormatter={value => `${Math.round(value*100)}%`} tick={{fontSize:11}} width={44}/><Tooltip formatter={(value) => pct(Number(value))}/><Area isAnimationActive={false} type="monotone" dataKey="drawdown" stroke="#b94b3b" fill="#f3deda" strokeWidth={2}/></AreaChart></ResponsiveContainer></div></section>
    <section className="data-panel"><header><span className="eyebrow">Composition</span><h2>Top holdings</h2></header>{snapshot.top_holdings.length ? <div className="table-scroll"><table><thead><tr><th>Symbol</th><th>Holding</th><th>Weight</th></tr></thead><tbody>{snapshot.top_holdings.map(item => <tr key={item.symbol ?? item.name}><td><strong>{item.symbol ?? '—'}</strong></td><td>{item.name}</td><td>{pct(item.weight)}</td></tr>)}</tbody></table></div> : <p className="missing">Holdings unavailable from the provider.</p>}</section>
    <section className="data-panel"><header><span className="eyebrow">Allocation</span><h2>Sector exposure</h2></header><div className="allocation-list">{Object.entries(snapshot.sectors).map(([name,value]) => <div key={name}><span>{name}</span><strong>{pct(value)}</strong><i><b style={{width:pct(value)}}/></i></div>)}</div></section>
  </div>
}

function ReportList({ reports }: { reports: Array<[string,string]> }) {
  if (!reports.length) return <div className="empty-state"><h2>No report content yet</h2><p>Sections appear here as agents complete their work.</p></div>
  const titles: Record<string,string> = { market_report:'Market Analysis', sentiment_report:'Sentiment Analysis', news_report:'News Analysis', fundamentals_report:'Fund Analysis', investment_plan:'Research Decision', trader_investment_plan:'Trading Plan', final_trade_decision:'Final Decision' }
  return <div className="report-list">{reports.map(([key,content]) => <article key={key}><header><span className="eyebrow">Agent report</span><h2>{titles[key] ?? key}</h2></header><div className="markdown"><ReactMarkdown skipHtml>{content}</ReactMarkdown></div></article>)}</div>
}
