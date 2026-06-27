const signalColors: Record<string, string> = {
  LIVE: 'badge-success',
  PRE_MARKET: 'badge-info',
  POST_CLOSE: 'badge-warning',
  EOD: 'badge-neutral',
  CLOSED: 'badge-ghost',
  OK: 'badge-success',
  WARN: 'badge-warning',
  ERROR: 'badge-error',
  'BUY-WATCH': 'badge-success',
  'ENTRY ZONE': 'badge-success',
  'WAIT FOR DIP': 'badge-info',
  HOLD: 'badge-neutral',
  TRIM: 'badge-warning',
  REDUCE: 'badge-warning',
  'EXIT WATCH': 'badge-error',
  'STOP LOSS HIT': 'badge-error',
  'NO LIQUID EXIT': 'badge-error',
  'DO NOT CHASE': 'badge-warning',
  AVOID: 'badge-error',
  HIGH: 'badge-error',
  INFO: 'badge-info',
};

export function StatusBadge({ value }: { value?: string | null }) {
  const text = value || 'n/a';
  return <span className={`badge badge-sm ${signalColors[text] ?? 'badge-outline'}`}>{text}</span>;
}

export function SignalBadge({ value }: { value?: string | null }) {
  const text = value || 'NO-DATA';
  return <span className={`badge badge-sm font-semibold ${signalColors[text] ?? 'badge-outline'}`}>{text}</span>;
}
