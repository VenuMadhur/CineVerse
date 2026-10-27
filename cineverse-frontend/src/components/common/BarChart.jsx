/**
 * Lightweight, dependency-free horizontal bar chart. Extracted from
 * AdminAnalyticsPage so it can be reused on the Admin Dashboard too,
 * following the same extraction already done for TrendChart.
 */
export default function BarChart({ items, colorClass = 'bg-[#E50914]', maxValue }) {
  const max = maxValue ?? Math.max(...items.map((i) => Number(i.value)), 1);
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <span className="w-28 shrink-0 truncate text-right text-xs text-slate-400">
            {item.label}
          </span>
          <div className="relative h-5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className={`h-full rounded-full transition-all duration-700 ${colorClass}`}
              style={{ width: `${Math.max((Number(item.value) / max) * 100, 0).toFixed(1)}%` }}
            />
          </div>
          <span className="w-20 shrink-0 text-xs font-medium text-white">
            {item.formatted ?? item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
