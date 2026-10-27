/**
 * Inline area/sparkline for compact KPI cards -- no axis labels, no
 * legend (TrendChart already covers that fuller case). Same hand-
 * rolled SVG technique as TrendChart, just compact for a KPI-card
 * context.
 *
 * area=true (default) renders a filled area under the line -- more
 * visually substantial than a bare line for a card-sized visual.
 * area=false keeps the original bare-line behavior for any future
 * caller that wants it. Default width/height increased from the
 * original 100x32 to 140x48 so the shape is actually visible at a
 * normal desktop viewing size, not a barely-there sliver.
 */
export default function MiniSparkline({
  values,
  colorClass = 'stroke-[#E50914] text-[#E50914]',
  fillClass,
  width = 140,
  height = 48,
  area = true,
}) {
  if (!values || values.length === 0) return null;

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const n = values.length;
  const padding = 4;
  const plotH = height - padding * 2;

  const xFor = (i) => (n <= 1 ? width / 2 : (i / (n - 1)) * width);
  const yFor = (v) => padding + plotH - ((v - min) / range) * plotH;

  const points = values.map((v, i) => `${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`);
  const linePoints = points.join(' ');
  const areaPoints = `${xFor(0).toFixed(1)},${height} ${linePoints} ${xFor(n - 1).toFixed(1)},${height}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-12 w-full" aria-hidden="true" preserveAspectRatio="none">
      {area && n > 1 && (
        <polygon
          points={areaPoints}
          className={fillClass || colorClass}
          fill="currentColor"
          fillOpacity="0.15"
          stroke="none"
        />
      )}
      {n > 1 ? (
        <polyline
          points={linePoints}
          fill="none"
          className={colorClass}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      ) : (
        <circle cx={xFor(0)} cy={yFor(values[0])} r="4" className={colorClass} fill="currentColor" />
      )}
      {n > 1 &&
        values.map((v, i) => (
          <circle key={i} cx={xFor(i)} cy={yFor(v)} r={i === n - 1 ? 3.5 : 2} className={colorClass} fill="currentColor" />
        ))}
    </svg>
  );
}
