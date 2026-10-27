import { useParams, Link, Navigate } from 'react-router-dom';
import { FiArrowLeft, FiFilm, FiLock } from 'react-icons/fi';
import { FullPageSpinner } from '../components/common/Spinner';
import { findCatalogItem, TIER_LABELS } from '../data/catalogData';
import { useAccessTier } from '../hooks/useAccessTier';

/**
 * Professional placeholder only -- no real streaming is implemented
 * anywhere in this feature. Access is re-checked here independently
 * of TitleDetailPage's own check, so navigating straight to this URL
 * can't bypass the subscription gate.
 */
export default function WatchNowPage() {
  const { id } = useParams();
  const item = findCatalogItem(id);
  const { loading, hasAccess } = useAccessTier();

  if (!item) {
    return <Navigate to="/movies" replace />;
  }

  if (loading) {
    return <FullPageSpinner />;
  }

  if (!hasAccess(item.requiredTier)) {
    return (
      <div className="animate-fade-in mx-auto max-w-lg py-16 text-center">
        <FiLock className="mx-auto mb-4 text-slate-500" size={40} />
        <h1 className="text-xl font-bold text-white">🔒 Premium Content</h1>
        <p className="mt-2 text-sm text-slate-400">
          This title requires the {TIER_LABELS[item.requiredTier]} plan.
        </p>
        <Link to="/plans" className="focus-ring btn-primary mt-6 inline-flex">
          Upgrade Plan
        </Link>
      </div>
    );
  }

  return (
    <div className="animate-fade-in mx-auto flex max-w-lg flex-col items-center py-16 text-center">
      <div className="icon-badge icon-badge-brand mb-5 h-16 w-16">
        <FiFilm size={28} />
      </div>
      <h1 className="text-xl font-bold text-white">{item.title}</h1>
      <p className="mt-1 text-sm font-semibold uppercase tracking-wide text-[#E50914]">
        Demo Streaming Experience
      </p>
      <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
        Streaming playback is intentionally not implemented because this project focuses on
        subscription billing, payments, invoices, refunds, and customer management.
      </p>
      <Link
        to={`/${item.type === 'series' ? 'series' : 'movies'}/${item.id}`}
        className="focus-ring btn-secondary mt-6 inline-flex items-center gap-2"
      >
        <FiArrowLeft size={16} /> Back to Details
      </Link>
    </div>
  );
}
