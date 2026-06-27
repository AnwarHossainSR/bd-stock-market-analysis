import { ArrowDownUp, Search } from 'lucide-react';
import type React from 'react';
import { useMemo, useState } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  sort?: (row: T) => string | number | null | undefined;
}

interface DataTableProps<T> {
  rows: T[];
  columns: Column<T>[];
  getKey: (row: T, index: number) => string;
  search?: (row: T) => string;
  empty?: string;
}

export function DataTable<T>({ rows, columns, getKey, search, empty = 'No rows.' }: DataTableProps<T>) {
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState(columns[0]?.key ?? '');
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q && search ? rows.filter((row) => search(row).toLowerCase().includes(q)) : rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sort) return filtered;
    return [...filtered].sort((a, b) => {
      const av = col.sort?.(a);
      const bv = col.sort?.(b);
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av ?? '').localeCompare(String(bv ?? ''));
      return direction === 'asc' ? cmp : -cmp;
    });
  }, [columns, direction, query, rows, search, sortKey]);

  const toggle = (key: string) => {
    if (key === sortKey) {
      setDirection(direction === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setDirection('desc');
    }
  };

  return (
    <div className="space-y-2">
      {search && (
        <label className="input input-sm input-bordered flex max-w-xs items-center gap-2">
          <Search size={14} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} className="grow" placeholder="Search ticker" />
        </label>
      )}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>
                  {column.sort ? (
                    <button className="btn btn-ghost btn-xs px-0" onClick={() => toggle(column.key)} type="button">
                      {column.header}
                      <ArrowDownUp size={12} />
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length ? (
              visible.map((row, index) => (
                <tr key={getKey(row, index)}>
                  {columns.map((column) => (
                    <td key={column.key}>{column.render(row)}</td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="py-6 text-center text-sm text-base-content/60">
                  {empty}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
