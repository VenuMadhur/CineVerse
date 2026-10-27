/**
 * Lightweight, dependency-free SVG donut chart. No charting library
 * added -- uses the standard stroke-dasharray/stroke-dashoffset ring
 * technique. Follows the same hand-rolled, CSS-var-themed approach as
 * BarChart/TrendChart.
 *
 * segments: [{ label, value, colorClass (a static Tailwind stroke-*
 *              class), dotClass (a static Tailwind bg-* class) }]
 * centerLabel / centerValue: optional text shown in the donut's hole
 * (e.g. a total count) -- must come from real, already-known data,
 * never invented.
 */
export default function DonutChart({ segments, size = 160, thickness = 18, centerLabel, centerValue }) {
  const total = segments.reduce((sum, s) => sum + Number(s.value), 0);
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let offsetSoFar = 0;

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
        <svg viewBox={`0 0 ${size} ${size}`} className="-rotate-90" width={size} height={size}>
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            className="stroke-white/[0.06]"
            strokeWidth={thickness}
          />
          {total > 0 &&
            segments
              .filter((s) => Number(s.value) > 0)
              .map((s) => {
                const fraction = Number(s.value) / total;
                const dash = fraction * circumference;
                const el = (
                  <circle
                    key={s.label}
                    cx={center}
                    cy={center}
                    r={radius}
                    fill="none"
                    className={s.colorClass}
                    strokeWidth={thickness}
                    strokeDasharray={`${dash} ${circumference - dash}`}
                    strokeDashoffset={-offsetSoFar}
                    strokeLinecap="butt"
                  />
                );
                offsetSoFar += dash;
                return el;
              })}
        </svg>
        {(centerLabel || centerValue != null) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {centerValue != null && <span className="text-xl font-bold text-white">{centerValue}</span>}
            {centerLabel && <span className="text-[10px] text-slate-500">{centerLabel}</span>}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        {segments.map((s) => (
          <div key={s.label} className="flex items-center gap-2 text-xs">
            <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${s.dotClass}`} />
            <span className="text-slate-400">{s.label}</span>
            <span className="font-medium text-white">{s.value}</span>
            {total > 0 && (
              <span className="text-slate-600">({((Number(s.value) / total) * 100).toFixed(0)}%)</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
