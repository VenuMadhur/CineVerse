/**
 * Minimal progress ring for compact KPI cards -- just the ring and a
 * center value, no legend list. Same stroke-dasharray technique as
 * DonutChart (not a new charting library), stripped down for a
 * small-card context.
 */
export default function MiniRing({ value, total, size = 44, thickness = 5, colorClass = 'stroke-emerald-400' }) {
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;
  const fraction = total > 0 ? Math.min(value / total, 1) : 0;
  const dash = fraction * circumference;

  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="-rotate-90" width={size} height={size} aria-hidden="true">
        <circle cx={center} cy={center} r={radius} fill="none" className="stroke-white/[0.08]" strokeWidth={thickness} />
        {fraction > 0 && (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            className={colorClass}
            strokeWidth={thickness}
            strokeDasharray={`${dash} ${circumference - dash}`}
            strokeLinecap="round"
          />
        )}
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white">
        {value}
      </div>
    </div>
  );
}
