import type { AlertsResult, AnalysisRun, DataHealth, PortfolioResult, ReportFile, SessionSheet } from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  actionSheet: () => request<SessionSheet>('/api/session/action-sheet'),
  portfolio: () => request<PortfolioResult>('/api/session/portfolio'),
  alerts: () => request<AlertsResult>('/api/session/alerts'),
  health: () => request<DataHealth>('/api/session/health'),
  reports: () => request<{ reports: ReportFile[] }>('/api/reports'),
  analysisRuns: () => request<{ runs: AnalysisRun[] }>('/api/analysis/runs'),
  latestAnalysis: () => request<AnalysisRun>('/api/analysis/runs/latest'),
  runAnalysis: () => request<AnalysisRun>('/api/analysis/runs', { method: 'POST' }),
  saveCommentary: (id: string, commentary_md: string) =>
    request<AnalysisRun>(`/api/analysis/runs/${id}/commentary`, {
      method: 'POST',
      body: JSON.stringify({ commentary_md }),
    }),
  captureIntraday: () => request<{ captured: number }>('/api/intraday/capture', { method: 'POST' }),
};
