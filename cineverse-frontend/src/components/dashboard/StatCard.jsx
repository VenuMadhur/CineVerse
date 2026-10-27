import { motion } from 'framer-motion';

const TONE_CLASS = {
  brand: 'icon-badge-brand',
  success: 'icon-badge-success',
  info: 'icon-badge-info',
  warning: 'icon-badge-warning',
  violet: 'icon-badge-violet',
};

export default function StatCard({
  icon: Icon,
  label,
  value,
  sublabel,
  accent = false,
  tone,
  trend, // optional: { direction: 'up'|'down'|'neutral', label: string } — caller-supplied, real data only
  visual, // optional: a small React node (e.g. MiniSparkline/MiniRing) rendered below the value — real data only
}) {
  const resolvedTone = tone || (accent ? 'brand' : null);
  const trendPillClass = trend
    ? {
        up: 'trend-pill trend-pill-up',
        down: 'trend-pill trend-pill-down',
        neutral: 'trend-pill trend-pill-neutral',
      }[trend.direction] || 'trend-pill trend-pill-neutral'
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`glass-card metric-card flex items-start justify-between gap-4 ${accent ? 'border-[#E50914]/30' : ''}`}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-semibold uppercase tracking-wide text-slate-500">
          {label}
        </p>
        <p className="mt-2 truncate text-2xl font-bold text-white">{value}</p>
        <div className="mt-1.5 flex items-center gap-2">
          {trend && <span className={trendPillClass}>{trend.label}</span>}
          {sublabel && <p className="truncate text-xs text-slate-500">{sublabel}</p>}
        </div>
        {visual && <div className="mt-2">{visual}</div>}
      </div>
      <div className={`icon-badge flex-shrink-0 ${resolvedTone ? TONE_CLASS[resolvedTone] : 'bg-white/[0.06] text-slate-300'}`}>
        <Icon size={18} />
      </div>
    </motion.div>
  );
}
