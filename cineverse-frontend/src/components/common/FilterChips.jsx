/**
 * Status/type filter chips, extracted (Phase 5e) from the identical
 * pattern that had been copy-pasted independently across
 * AdminAuditLogPage, AdminPlansPage, and AdminSubscriptionsPage --
 * one of them (AdminSubscriptionsPage) had drifted and was missing
 * `focus-ring`, so keyboard users got no visible focus indicator
 * there specifically. Extracting this means that can't happen again.
 *
 * `formatLabel` is optional -- defaults to "the option, or 'All' for
 * the empty-string option" (every existing caller's most common
 * case); pass a custom formatter for anything more specific (e.g.
 * replacing underscores in a status value).
 */
export default function FilterChips({ options, value, onChange, formatLabel }) {
  return (
    <div className="mb-6 flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option || 'all'}
          onClick={() => onChange(option)}
          className={`focus-ring rounded-lg px-4 py-1.5 text-sm font-medium capitalize transition-colors ${
            value === option
              ? 'bg-amber-500/15 text-amber-400'
              : 'text-slate-400 hover:bg-white/[0.06] hover:text-white'
          }`}
        >
          {formatLabel ? formatLabel(option) : option || 'All'}
        </button>
      ))}
    </div>
  );
}
