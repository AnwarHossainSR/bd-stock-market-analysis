import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const sheet = {
  generated_at: '2026-06-28T11:00:00+06:00',
  market_state: 'LIVE',
  data_health: { status: 'OK', rows: 3, warnings: [] },
  market: { regime: 'MIXED', advances: 2, declines: 1, unchanged: 0, total_value_mn: 20 },
  top_value_movers: [{ code: 'ABC', ltp: 10, pct_change: 2, value_mn: 8 }],
  top_gainers: [{ code: 'ABC', ltp: 10, pct_change: 2, value_mn: 8 }],
  top_losers: [{ code: 'XYZ', ltp: 9, pct_change: -3, value_mn: 3 }],
  unusual_volume: [],
  buy_watch: [{ code: 'ABC', ltp: 10, pct_change: 2, value_mn: 8, label: 'BUY-WATCH', reason: 'volume' }],
  auto_watchlist: [{ code: 'ABC', entry_below: 9, breakout_above: 11, stop: 8.5, notes: 'auto' }],
  avoid_chase_warnings: [],
  portfolio: {
    summary: { positions: 1, market_value: 1000, unrealized_pnl: 50, return_pct: 5 },
    positions: [{ code: 'HOLD1', signal: 'HOLD', ltp: 10, pnl_pct: 5, liquidity_risk: 'LOW' }],
    danger: [],
    disclaimer: 'Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.',
  },
  portfolio_danger_names: [],
  disclaimer: 'Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.',
};

function mockFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes('/api/session/action-sheet')) return new Response(JSON.stringify(sheet));
      if (url.includes('/api/session/alerts')) return new Response(JSON.stringify({ count: 0, alerts: [], disclaimer: sheet.disclaimer }));
      if (url.includes('/api/session/health')) return new Response(JSON.stringify({ status: 'OK', rows: 3, warnings: [] }));
      if (url.includes('/api/reports')) return new Response(JSON.stringify({ reports: [{ file: 'report.pdf', url: '/reports/report.pdf', kind: 'pdf', size: 10, modified_at: 'now' }] }));
      if (url.includes('/api/analysis/runs') && init?.method === 'POST') return new Response(JSON.stringify({ id: '1', created_at: 'now', source: 'ui', summary_md: 'summary', report_status: 'ok', disclaimer: sheet.disclaimer }));
      if (url.includes('/api/analysis/runs')) return new Response(JSON.stringify({ runs: [] }));
      return new Response('{}');
    }) as any,
  );
}

describe('App', () => {
  beforeEach(mockFetch);
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders dashboard data and health status', async () => {
    render(<App />);
    expect(await screen.findByText('DSE Trading Desk')).toBeInTheDocument();
    expect(screen.getByText('LIVE')).toBeInTheDocument();
    expect(screen.getByText('MIXED')).toBeInTheDocument();
  });

  it('renders portfolio signal labels', async () => {
    render(<App />);
    fireEvent.click((await screen.findAllByRole('button', { name: /Portfolio/i }))[0]);
    expect(await screen.findByText('HOLD1')).toBeInTheDocument();
    expect(screen.getByText('HOLD')).toBeInTheDocument();
  });

  it('shows buy-watch rows and report links', async () => {
    render(<App />);
    fireEvent.click((await screen.findAllByRole('button', { name: /Buy-Watch/i }))[0]);
    expect(await screen.findByText('BUY-WATCH')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /Reports & Analysis/i })[0]);
    expect(await screen.findByText('report.pdf')).toBeInTheDocument();
  });

  it('runs analysis and shows saved summary', async () => {
    render(<App />);
    fireEvent.click((await screen.findAllByRole('button', { name: /^Run Analysis$/i }))[0]);
    await waitFor(() => expect(screen.getByText('summary')).toBeInTheDocument());
  });
});
