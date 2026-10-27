import { titleCase } from '../../utils/formatters';

const STATUS_STYLES = {
  // greens
  active: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  paid: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  succeeded: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  completed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  // ambers
  trial: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  pending: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  open: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  past_due: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  paused: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  draft: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  // reds
  failed: 'bg-red-500/15 text-red-400 border-red-500/30',
  cancelled: 'bg-red-500/15 text-red-400 border-red-500/30',
  void: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  // blues
  refunded: 'bg-sky-500/15 text-sky-400 border-sky-500/30',
};

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-slate-500/15 text-slate-400 border-slate-500/30';
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${style}`}
    >
      {titleCase(status)}
    </span>
  );
}
