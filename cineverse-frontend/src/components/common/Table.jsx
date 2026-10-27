export default function Table({ columns, children }) {
  return (
    <div className="glass-card overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
            {columns.map((col) => (
              <th key={col} className="whitespace-nowrap px-5 py-3 font-medium">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.06]">{children}</tbody>
      </table>
    </div>
  );
}

export function TableRow({ children, onClick }) {
  return (
    <tr
      onClick={onClick}
      className={`transition-colors hover:bg-white/[0.03] ${onClick ? 'cursor-pointer' : ''}`}
    >
      {children}
    </tr>
  );
}

export function TableCell({ children, className = '' }) {
  return <td className={`whitespace-nowrap px-5 py-3.5 text-slate-300 ${className}`}>{children}</td>;
}
