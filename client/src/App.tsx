import { AlertTriangle, BarChart3, FileText, HeartPulse, LineChart, Play, ShieldAlert, WalletCards } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { SignalBadge, StatusBadge } from './components/Badges';
import { DataTable, type Column } from './components/DataTable';
import { Disclaimer, EmptyState, ErrorPanel, MetricStrip, RefreshButton } from './components/Common';
import type { AlertRow, AnalysisRun, AutoWatchRow, DataHealth, PortfolioPosition, PriceRow, ReportFile, SessionSheet } from './types';

const tabs = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  { id: 'portfolio', label: 'Portfolio', icon: WalletCards },
  { id: 'buy', label: 'Buy-Watch', icon: LineChart },
  { id: 'risk', label: 'Avoid / Risk', icon: ShieldAlert },
  { id: 'alerts', label: 'Alerts', icon: AlertTriangle },
  { id: 'reports', label: 'Reports & Analysis', icon: FileText },
  { id: 'health', label: 'Data Health', icon: HeartPulse },
] as const;

type TabId = (typeof tabs)[number]['id'];

function fmt(value: unknown, suffix = '') {
  if (value === null || value === undefined || value === '') return 'n/a';
  if (typeof value === 'number') return `${Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix}`;
  return String(value);
}

function priceColumns(): Column<PriceRow>[] {
  return [
    { key: 'code', header: 'Code', render: (r) => <strong>{r.code}</strong>, sort: (r) => r.code },
    { key: 'ltp', header: 'LTP', render: (r) => fmt(r.ltp), sort: (r) => r.ltp },
    { key: 'pct', header: 'Change', render: (r) => fmt(r.pct_change, '%'), sort: (r) => r.pct_change },
    { key: 'value', header: 'Value mn', render: (r) => fmt(r.value_mn), sort: (r) => r.value_mn },
    { key: 'volume', header: 'Volume', render: (r) => fmt(r.volume), sort: (r) => r.volume },
    { key: 'label', header: 'Label', render: (r) => (r.label ? <SignalBadge value={r.label} /> : 'n/a'), sort: (r) => r.label },
    { key: 'reason', header: 'Reason', render: (r) => r.reason || 'n/a' },
  ];
}

function App() {
  const [active, setActive] = useState<TabId>('dashboard');
  const [sheet, setSheet] = useState<SessionSheet | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [health, setHealth] = useState<DataHealth | null>(null);
  const [reports, setReports] = useState<ReportFile[]>([]);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [commentary, setCommentary] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSheet, nextAlerts, nextHealth, nextReports, nextRuns] = await Promise.all([
        api.actionSheet(),
        api.alerts(),
        api.health(),
        api.reports(),
        api.analysisRuns().catch(() => ({ runs: [] })),
      ]);
      setSheet(nextSheet);
      setAlerts(nextAlerts.alerts);
      setHealth(nextHealth);
      setReports(nextReports.reports);
      setRuns(nextRuns.runs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'API offline');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const runAnalysis = async () => {
    setAnalysisLoading(true);
    setError(null);
    try {
      const run = await api.runAnalysis();
      setRuns((prev) => [run, ...prev.filter((x) => x.id !== run.id)]);
      setActive('reports');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setAnalysisLoading(false);
    }
  };

  const saveCommentary = async () => {
    if (!runs[0]) return;
    const updated = await api.saveCommentary(runs[0].id, commentary);
    setRuns((prev) => prev.map((run) => (run.id === updated.id ? updated : run)));
  };

  const market = sheet?.market;
  const portfolio = sheet?.portfolio;
  const disclaimer = sheet?.disclaimer || health?.disclaimer;

  return (
    <div data-theme="trader" className="min-h-screen bg-base-200 text-base-content">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 border-r border-base-300 bg-base-100 p-4 lg:block">
          <h1 className="text-xl font-bold">DSE Trading Desk</h1>
          <p className="mt-1 text-xs text-base-content/60">Live-session decision support</p>
          <nav className="mt-6 space-y-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button key={tab.id} className={`btn btn-sm w-full justify-start ${active === tab.id ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setActive(tab.id)} type="button">
                  <Icon size={16} />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </aside>

        <main className="w-full p-3 md:p-5">
          <header className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-bold">{tabs.find((t) => t.id === active)?.label}</h2>
                <StatusBadge value={sheet?.market_state} />
                <StatusBadge value={sheet?.data_health?.status} />
              </div>
              <p className="text-sm text-base-content/60">Generated {sheet?.generated_at || 'n/a'}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-sm btn-primary" onClick={runAnalysis} disabled={analysisLoading} type="button">
                <Play size={16} />
                {analysisLoading ? 'Running...' : 'Run Analysis'}
              </button>
              <RefreshButton onClick={load} loading={loading} />
            </div>
          </header>

          <div className="mb-4 flex gap-2 overflow-x-auto lg:hidden">
            {tabs.map((tab) => (
              <button key={tab.id} className={`btn btn-sm shrink-0 ${active === tab.id ? 'btn-primary' : 'btn-outline'}`} onClick={() => setActive(tab.id)} type="button">
                {tab.label}
              </button>
            ))}
          </div>

          {error && <ErrorPanel message={error} />}
          {!error && !sheet && <EmptyState message="Loading dashboard data..." />}
          {sheet && (
            <section className="space-y-5">
              {active === 'dashboard' && <Dashboard sheet={sheet} />}
              {active === 'portfolio' && <PortfolioPage positions={portfolio?.positions ?? []} summary={portfolio?.summary} />}
              {active === 'buy' && <BuyWatchPage buy={sheet.buy_watch} auto={sheet.auto_watchlist ?? []} />}
              {active === 'risk' && <RiskPage avoid={sheet.avoid_chase_warnings} danger={sheet.portfolio_danger_names} />}
              {active === 'alerts' && <AlertsPage alerts={alerts} />}
              {active === 'reports' && <ReportsPage reports={reports} runs={runs} commentary={commentary} setCommentary={setCommentary} saveCommentary={saveCommentary} analysisLoading={analysisLoading} runAnalysis={runAnalysis} />}
              {active === 'health' && <HealthPage health={health ?? sheet.data_health} />}
              <Disclaimer text={disclaimer} />
            </section>
          )}
        </main>
      </div>
    </div>
  );
}

function Dashboard({ sheet }: { sheet: SessionSheet }) {
  const market = sheet.market;
  return (
    <>
      <MetricStrip
        items={[
          { label: 'Regime', value: market.regime },
          { label: 'Advances', value: market.advances },
          { label: 'Declines', value: market.declines },
          { label: 'Unchanged', value: market.unchanged },
          { label: 'Value mn', value: fmt(market.total_value_mn) },
          { label: 'Rows', value: sheet.data_health.rows ?? 'n/a' },
        ]}
      />
      <DataTable rows={sheet.top_value_movers} columns={priceColumns()} getKey={(row, i) => `${row.code}-${i}`} search={(row) => row.code} empty="No value movers." />
      <div className="grid gap-4 xl:grid-cols-2">
        <DataTable rows={sheet.top_gainers} columns={priceColumns().slice(0, 4)} getKey={(row, i) => `g-${row.code}-${i}`} search={(row) => row.code} empty="No gainers." />
        <DataTable rows={sheet.top_losers} columns={priceColumns().slice(0, 4)} getKey={(row, i) => `l-${row.code}-${i}`} search={(row) => row.code} empty="No losers." />
      </div>
    </>
  );
}

function PortfolioPage({ positions, summary }: { positions: PortfolioPosition[]; summary?: any }) {
  const cols: Column<PortfolioPosition>[] = [
    { key: 'code', header: 'Code', render: (r) => <strong>{r.code}</strong>, sort: (r) => r.code },
    { key: 'signal', header: 'Signal', render: (r) => <SignalBadge value={r.signal} />, sort: (r) => r.signal },
    { key: 'ltp', header: 'LTP', render: (r) => fmt(r.ltp), sort: (r) => r.ltp },
    { key: 'pnl', header: 'P&L %', render: (r) => fmt(r.pnl_pct, '%'), sort: (r) => r.pnl_pct },
    { key: 'day', header: 'Day %', render: (r) => fmt(r.day_change_pct, '%'), sort: (r) => r.day_change_pct },
    { key: 'trend', header: 'Trend', render: (r) => r.trend || 'n/a', sort: (r) => r.trend },
    { key: 'sma', header: 'SMA', render: (r) => r.vs_sma20 || r.vs_sma50 || 'n/a' },
    { key: 'stop', header: 'Stop', render: (r) => fmt(r.atr_trailing_stop), sort: (r) => r.atr_trailing_stop },
    { key: 'risk', header: 'Liquidity', render: (r) => <StatusBadge value={r.liquidity_risk} />, sort: (r) => r.liquidity_risk },
  ];
  return (
    <>
      <MetricStrip
        items={[
          { label: 'Positions', value: summary?.positions ?? positions.length },
          { label: 'Market Value', value: fmt(summary?.market_value) },
          { label: 'Unrealized P&L', value: fmt(summary?.unrealized_pnl) },
          { label: 'Return', value: fmt(summary?.return_pct, '%') },
        ]}
      />
      <DataTable rows={positions} columns={cols} getKey={(row) => row.code} search={(row) => row.code} empty="No portfolio positions loaded." />
    </>
  );
}

function BuyWatchPage({ buy, auto }: { buy: PriceRow[]; auto: AutoWatchRow[] }) {
  const autoCols: Column<AutoWatchRow>[] = [
    { key: 'code', header: 'Code', render: (r) => <strong>{r.code}</strong>, sort: (r) => r.code },
    { key: 'entry', header: 'Entry <=', render: (r) => fmt(r.entry_below), sort: (r) => r.entry_below },
    { key: 'breakout', header: 'Breakout >', render: (r) => fmt(r.breakout_above), sort: (r) => r.breakout_above },
    { key: 'stop', header: 'Stop', render: (r) => fmt(r.stop), sort: (r) => r.stop },
    { key: 'notes', header: 'Notes', render: (r) => r.notes },
  ];
  return (
    <div className="space-y-5">
      <DataTable rows={buy} columns={priceColumns()} getKey={(row, i) => `${row.code}-${i}`} search={(row) => row.code} empty="Nothing clean today." />
      <DataTable rows={auto} columns={autoCols} getKey={(row) => row.code} search={(row) => row.code} empty="No auto watchlist rows." />
    </div>
  );
}

function RiskPage({ avoid, danger }: { avoid: PriceRow[]; danger: PortfolioPosition[] }) {
  const dangerCols: Column<PortfolioPosition>[] = [
    { key: 'code', header: 'Code', render: (r) => <strong>{r.code}</strong>, sort: (r) => r.code },
    { key: 'signal', header: 'Signal', render: (r) => <SignalBadge value={r.signal} />, sort: (r) => r.signal },
    { key: 'pnl', header: 'P&L', render: (r) => fmt(r.pnl_pct, '%'), sort: (r) => r.pnl_pct },
    { key: 'support', header: 'Support Risk', render: (r) => <StatusBadge value={r.support_break_risk} />, sort: (r) => r.support_break_risk },
    { key: 'liquidity', header: 'Liquidity', render: (r) => <StatusBadge value={r.liquidity_risk} />, sort: (r) => r.liquidity_risk },
  ];
  return (
    <div className="space-y-5">
      <DataTable rows={danger} columns={dangerCols} getKey={(row) => row.code} search={(row) => row.code} empty="No portfolio danger names." />
      <DataTable rows={avoid} columns={priceColumns()} getKey={(row, i) => `${row.code}-${i}`} search={(row) => row.code} empty="No avoid/chase warnings." />
    </div>
  );
}

function AlertsPage({ alerts }: { alerts: AlertRow[] }) {
  const cols: Column<AlertRow>[] = [
    { key: 'severity', header: 'Severity', render: (r) => <StatusBadge value={r.severity} />, sort: (r) => (r.severity === 'HIGH' ? 3 : r.severity === 'WARN' ? 2 : 1) },
    { key: 'code', header: 'Code', render: (r) => <strong>{r.code}</strong>, sort: (r) => r.code },
    { key: 'type', header: 'Type', render: (r) => r.type, sort: (r) => r.type },
    { key: 'message', header: 'Message', render: (r) => r.message },
  ];
  return <DataTable rows={alerts} columns={cols} getKey={(row, i) => `${row.code}-${row.type}-${i}`} search={(row) => `${row.code} ${row.type}`} empty="No alerts." />;
}

function ReportsPage(props: { reports: ReportFile[]; runs: AnalysisRun[]; commentary: string; setCommentary: (value: string) => void; saveCommentary: () => void; analysisLoading: boolean; runAnalysis: () => void }) {
  const reportCols: Column<ReportFile>[] = [
    { key: 'file', header: 'File', render: (r) => <a className="link" href={r.url} target="_blank" rel="noreferrer">{r.file}</a>, sort: (r) => r.file },
    { key: 'kind', header: 'Kind', render: (r) => r.kind, sort: (r) => r.kind },
    { key: 'modified', header: 'Modified', render: (r) => r.modified_at, sort: (r) => r.modified_at },
    { key: 'size', header: 'Size', render: (r) => fmt(r.size), sort: (r) => r.size },
  ];
  const runCols: Column<AnalysisRun>[] = [
    { key: 'time', header: 'Created', render: (r) => r.created_at, sort: (r) => r.created_at },
    { key: 'source', header: 'Source', render: (r) => r.source, sort: (r) => r.source },
    { key: 'status', header: 'Report', render: (r) => <StatusBadge value={r.report_status} />, sort: (r) => r.report_status },
    { key: 'file', header: 'PDF', render: (r) => (r.report_url ? <a className="link" href={r.report_url} target="_blank" rel="noreferrer">{r.report_file}</a> : 'n/a') },
  ];
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary btn-sm" onClick={props.runAnalysis} disabled={props.analysisLoading} type="button">
          <Play size={16} />
          {props.analysisLoading ? 'Running analysis...' : 'Run Analysis'}
        </button>
      </div>
      <DataTable rows={props.runs} columns={runCols} getKey={(row) => row.id} search={(row) => `${row.source} ${row.report_file ?? ''}`} empty="No saved analysis runs yet." />
      {props.runs[0] && (
        <div className="rounded border border-base-300 bg-base-100 p-4">
          <h3 className="font-semibold">Latest Analysis Summary</h3>
          <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-xs">{props.runs[0].summary_md}</pre>
          <textarea className="textarea textarea-bordered mt-3 w-full" value={props.commentary} onChange={(e) => props.setCommentary(e.target.value)} placeholder="Paste Codex/Claude /analysis commentary here" />
          <button className="btn btn-sm btn-outline mt-2" onClick={props.saveCommentary} type="button">Save Commentary</button>
        </div>
      )}
      <DataTable rows={props.reports} columns={reportCols} getKey={(row) => row.file} search={(row) => row.file} empty="No reports found." />
    </div>
  );
}

function HealthPage({ health }: { health: DataHealth }) {
  return (
    <>
      <MetricStrip
        items={[
          { label: 'Status', value: <StatusBadge value={health.status} /> },
          { label: 'Rows', value: fmt(health.rows) },
          { label: 'Zero LTP', value: fmt(health.zero_ltp) },
          { label: 'Cache Age', value: fmt(health.cache_age_seconds, 's') },
          { label: 'DB Latest', value: health.db_latest_date || 'n/a' },
          { label: 'Intraday Latest', value: health.intraday_latest_ts || 'n/a' },
        ]}
      />
      {(health.warnings ?? []).length ? <div className="alert alert-warning">{health.warnings?.join(', ')}</div> : <EmptyState message="No data-health warnings." />}
    </>
  );
}

export default App;
