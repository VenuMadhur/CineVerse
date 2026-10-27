/**
 * A glass-card section with an icon + uppercase label header, followed
 * by content. Extracted from the pattern AdminReportsPage already used
 * ad hoc (Phase 5c) so it's reusable rather than copy-pasted. Reuses
 * the existing `glass-card` theme class -- no new visual language.
 */
export default function SectionCard({ icon: Icon, label, accent = 'amber', action, className = '', children }) {
  const accentClass =
    {
      amber: 'text-amber-400',
      brand: 'text-[#E50914]',
      slate: 'text-slate-400',
      success: 'text-emerald-400',
      info: 'text-sky-400',
      violet: 'text-violet-400',
    }[accent] || 'text-amber-400';

  return (
    <div className={`glass-card p-6 ${className}`}>
      {(Icon || label || action) && (
        <div className="mb-5 flex items-center justify-between gap-3">
          <div className={`flex items-center gap-3 ${accentClass}`}>
            {Icon && <Icon size={20} />}
            {label && <span className="text-sm font-semibold uppercase tracking-wide">{label}</span>}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}
