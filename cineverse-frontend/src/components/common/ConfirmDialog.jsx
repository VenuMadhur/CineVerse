import Modal from './Modal';
import Spinner from './Spinner';

/**
 * Reusable confirmation dialog -- replaces native `window.confirm()`
 * calls with something that actually matches the app's design system
 * (and works with a loading state, unlike a blocking browser dialog).
 *
 * `variant="danger"` renders the confirm button in the destructive
 * red style (archiving, cancelling, etc.); the default variant uses
 * the standard primary button style for non-destructive confirmations.
 */
export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = 'Are you sure?',
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  loading = false,
}) {
  return (
    <Modal open={open} onClose={onClose} title={title} maxWidth="max-w-md">
      {message && <p className="mb-6 text-sm text-slate-300">{message}</p>}
      <div className="flex gap-3">
        <button onClick={onClose} disabled={loading} className="btn-secondary flex-1">
          {cancelLabel}
        </button>
        <button
          onClick={onConfirm}
          disabled={loading}
          className={
            variant === 'danger'
              ? 'focus-ring inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 px-5 py-2.5 font-semibold text-white transition-all duration-200 hover:bg-red-500 active:scale-95 disabled:opacity-50 disabled:pointer-events-none'
              : 'btn-primary flex-1'
          }
        >
          {loading ? <Spinner size="sm" /> : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
