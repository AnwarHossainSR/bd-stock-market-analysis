import { RefreshCw } from 'lucide-react';
import type React from 'react';

export function MetricStrip({ items }: { items: Array<{ label: string; value: React.ReactNode }> }) {
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-6">
      {items.map((item) => (
        <div key={item.label} className="rounded border border-base-300 bg-base-100 p-3">
          <div className="text-xs uppercase tracking-wide text-base-content/60">{item.label}</div>
          <div className="mt-1 text-lg font-semibold">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <div className="rounded border border-dashed border-base-300 bg-base-100 p-6 text-center text-sm text-base-content/60">{message}</div>;
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <div role="alert" className="alert alert-error">
      <span>{message}</span>
      <span className="text-xs">Start backend: .venv\Scripts\uvicorn api.main:app --port 8000</span>
    </div>
  );
}

export function RefreshButton({ onClick, loading }: { onClick: () => void; loading?: boolean }) {
  return (
    <button className="btn btn-sm btn-outline" onClick={onClick} disabled={loading} type="button" title="Refresh market data">
      <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
      Refresh
    </button>
  );
}

export function Disclaimer({ text }: { text?: string }) {
  return <p className="mt-6 text-xs text-base-content/60">{text || 'Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.'}</p>;
}
