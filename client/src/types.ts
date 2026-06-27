export type Status = 'OK' | 'WARN' | 'ERROR' | string;

export type MarketState = 'PRE_MARKET' | 'LIVE' | 'POST_CLOSE' | 'EOD' | 'CLOSED' | string;

export interface PriceRow {
  code: string;
  ltp?: number | null;
  high?: number | null;
  low?: number | null;
  pct_change?: number | null;
  value_mn?: number | null;
  volume?: number | null;
  trades?: number | null;
  label?: string;
  reason?: string;
  volume_ratio?: number | null;
}

export interface AutoWatchRow {
  code: string;
  entry_below: number;
  breakout_above: number;
  stop: number;
  notes: string;
}

export interface DataHealth {
  status: Status;
  latest_scrape?: string;
  rows?: number;
  zero_ltp?: number;
  warnings?: string[];
  cache_age_seconds?: number | null;
  missing_portfolio_prices?: string[];
  db_latest_date?: string | null;
  intraday_latest_ts?: string | null;
  disclaimer?: string;
}

export interface MarketSummary {
  regime: string;
  advances: number;
  declines: number;
  unchanged: number;
  total?: number;
  total_value_mn: number;
}

export interface PortfolioPosition {
  code: string;
  quantity?: number;
  buy_price?: number | null;
  ltp?: number | null;
  market_value?: number | null;
  unrealized_pnl?: number | null;
  pnl_pct?: number | null;
  day_change_pct?: number | null;
  score?: number | null;
  signal?: string;
  trend?: string | null;
  rsi_zone?: string | null;
  vs_sma20?: string | null;
  vs_sma50?: string | null;
  atr_trailing_stop?: number | null;
  support?: number | null;
  resistance?: number | null;
  support_break_risk?: string;
  liquidity_risk?: string;
  concentration_risk?: string;
  portfolio_weight_pct?: number | null;
  notes?: string[];
}

export interface PortfolioResult {
  summary: {
    positions: number;
    invested?: number;
    market_value?: number;
    unrealized_pnl?: number;
    return_pct?: number | null;
  };
  positions: PortfolioPosition[];
  danger: PortfolioPosition[];
  disclaimer: string;
}

export interface SessionSheet {
  generated_at: string;
  market_state: MarketState;
  data_health: DataHealth;
  market: MarketSummary;
  top_value_movers: PriceRow[];
  top_gainers: PriceRow[];
  top_losers: PriceRow[];
  unusual_volume: PriceRow[];
  buy_watch: PriceRow[];
  auto_watchlist?: AutoWatchRow[];
  avoid_chase_warnings: PriceRow[];
  portfolio?: PortfolioResult | null;
  portfolio_danger_names: PortfolioPosition[];
  disclaimer: string;
}

export interface AlertRow {
  type: string;
  severity: 'HIGH' | 'WARN' | 'INFO' | string;
  code: string;
  message: string;
}

export interface AlertsResult {
  count: number;
  watchlist_source?: { auto: number; manual: number; merged: number };
  alerts: AlertRow[];
  disclaimer: string;
}

export interface ReportFile {
  file: string;
  url: string;
  kind: string;
  size: number;
  modified_at: string;
}

export interface AnalysisRun {
  id: string;
  created_at: string;
  source: string;
  market_state?: string | null;
  payload_json?: any;
  summary_md?: string;
  commentary_md?: string;
  report_file?: string | null;
  report_url?: string | null;
  report_status?: string;
  report_error?: string | null;
  disclaimer: string;
}
