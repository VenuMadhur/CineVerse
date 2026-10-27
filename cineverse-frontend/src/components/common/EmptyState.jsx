import { FiAlertCircle, FiInbox } from 'react-icons/fi';

export function EmptyState({ icon: Icon = FiInbox, title, description }) {
  return (
    <div className="animate-fade-in flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-white/[0.02] px-6 py-16 text-center">
      <Icon className="mb-3 text-slate-500" size={40} />
      <p className="text-base font-semibold text-slate-300">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
    </div>
  );
}

export function ErrorState({ message = 'Something went wrong.', onRetry }) {
  return (
    <div className="animate-fade-in flex flex-col items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/[0.04] px-6 py-16 text-center">
      <FiAlertCircle className="mb-3 text-red-400" size={40} />
      <p className="text-base font-semibold text-red-300">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary mt-4">
          Try again
        </button>
      )}
    </div>
  );
}
