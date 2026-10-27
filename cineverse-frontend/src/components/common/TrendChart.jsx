import { useState } from 'react';

/**
 * Lightweight, dependency-free multi-series SVG line chart. No
 * charting library added -- follows the same "hand-rolled, CSS-var
 * themed" approach already established by the admin analytics page's
 * BarChart, just for time series instead of categorical data.
 * Extracted here so both the customer and admin dashboards can reuse
 * the exact same component rather than duplicating it.
 *
 * series: [{ label, colorClass (Tailwind stroke-x / text-x classes),
 *            dotClass (a static Tailwind bg-* class -- must be a
 *            literal string at the call site, not derived at runtime,
 *            or Tailwind's JIT scanner won't generate the CSS for it),
 *            values: number[] }]
 * xLabels: string[] (same length as each series' values)
 * formatValue: optional (value) => string, used in the hover tooltip
 *              (e.g. currency formatting). Defaults to the raw number
 *              if omitted, so existing callers need no changes.
 */
export default function TrendChart({
  series,
  xLabels,
  height = 160,
  ariaLabel = 'Trend chart',
  formatValue = (v) => String(v),
}) {
  const [hoverIndex, setHoverIndex] = useState(null);
  const width = 600;
  const padding = { top: 12, right: 12, bottom: 24, left: 12 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const allValues = series.flatMap((s) => s.values);
  const max = Math.max(...allValues, 1);
  const min = Math.min(...allValues, 0);
  const range = max - min || 1;
  const n = xLabels.length;

  const xFor = (i) => padding.left + (n <= 1 ? 0 : (i / (n - 1)) * plotW);
  const yFor = (v) => padding.top + plotH - ((v - min) / range) * plotH;

  const pointsFor = (values) => values.map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`).join(' ');

  const zeroY = yFor(0);
  const colWidth = n > 1 ? plotW / (n - 1) : plotW;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={ariaLabel}>
        {min < 0 && max > 0 && (
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={zeroY}
            y2={zeroY}
            className="stroke-white/15"
            strokeWidth="1"
            strokeDasharray="4 3"
          />
        )}
        {hoverIndex != null && (
          <line
            x1={xFor(hoverIndex)}
            x2={xFor(hoverIndex)}
            y1={padding.top}
            y2={padding.top + plotH}
            className="stroke-white/20"
            strokeWidth="1"
          />
        )}
        {series.map((s) => (
          <polyline
            key={s.label}
            points={pointsFor(s.values)}
            fill="none"
            className={s.colorClass}
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}
        {series.map((s) =>
          s.values.map((v, i) => (
            <circle
              key={`${s.label}-${i}`}
              cx={xFor(i)}
              cy={yFor(v)}
              r={hoverIndex === i ? 4 : 2.5}
              className={s.colorClass}
              fill="currentColor"
            />
          ))
        )}
        {/* Invisible per-column hit targets, driving the hover tooltip
            -- one wide rect per data point rather than requiring the
            cursor to land exactly on a 2.5px-radius circle. */}
        {xLabels.map((_, i) => (
          <rect
            key={`hit-${i}`}
            x={xFor(i) - colWidth / 2}
            y={padding.top}
            width={colWidth}
            height={plotH}
            fill="transparent"
            onMouseEnter={() => setHoverIndex(i)}
            onMouseLeave={() => setHoverIndex((cur) => (cur === i ? null : cur))}
          />
        ))}
      </svg>

      {hoverIndex != null && (
        <div
          className="glass-card pointer-events-none absolute z-10 -translate-x-1/2 !rounded-lg px-3 py-2 text-xs shadow-lg"
          style={{
            left: `${(xFor(hoverIndex) / width) * 100}%`,
            top: 0,
          }}
        >
          <p className="mb-1 font-semibold text-white">{xLabels[hoverIndex]}</p>
          {series.map((s) => (
            <p key={s.label} className="flex items-center gap-1.5 text-slate-300">
              <span className={`h-1.5 w-1.5 rounded-full ${s.dotClass}`} />
              {s.label}: <span className="font-medium text-white">{formatValue(s.values[hoverIndex])}</span>
            </p>
          ))}
        </div>
      )}

      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        {xLabels.map((l, i) => (
          <span key={i} className={n > 8 && i % 2 !== 0 ? 'hidden sm:inline' : ''}>
            {l}
          </span>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-4">
        {series.map((s) => (
          <span key={s.label} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className={`h-2 w-2 rounded-full ${s.dotClass}`} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
