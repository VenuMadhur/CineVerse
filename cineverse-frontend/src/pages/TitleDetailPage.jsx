import { useParams, Link, Navigate } from 'react-router-dom';
import { FiArrowLeft, FiPlay, FiStar, FiLock, FiCalendar, FiClock, FiGlobe, FiUsers } from 'react-icons/fi';
import PosterPlaceholder from '../components/catalog/PosterPlaceholder';
import Spinner from '../components/common/Spinner';
import { findCatalogItem, TIER_LABELS } from '../data/catalogData';
import { useAccessTier } from '../hooks/useAccessTier';

const TIER_BADGE_CLASS = {
  starter: 'trend-pill trend-pill-neutral',
  professional: 'trend-pill trend-pill-up',
  premium: 'trend-pill bg-[#E50914]/15 text-[#ff4d55]',
};

/**
 * Shared detail page for both /movies/:id and /series/:id. Access
 * gating reuses the existing customer subscription/plan data via
 * useAccessTier() -- no new entitlement concept, no backend change.
 * "Watch Now" opens a local placeholder route; "Preview" opens a
 * separate in-app placeholder -- neither embeds or links to any real
 * video content anywhere in this feature.
 */
export default function TitleDetailPage() {
  const { id } = useParams();
  const item = findCatalogItem(id);
  const { loading: tierLoading, hasAccess } = useAccessTier();

  if (!item) {
    return <Navigate to="/movies" replace />;
  }

  const backHref = item.type === 'series' ? '/series' : '/movies';
  const canWatch = hasAccess(item.requiredTier);

  return (
    <div className="animate-fade-in">
      <Link
        to={backHref}
        className="focus-ring mb-6 inline-flex items-center gap-2 rounded-lg text-sm text-slate-400 hover:text-white"
      >
        <FiArrowLeft size={16} /> Back to {item.type === 'series' ? 'Web Series' : 'Movies'}
      </Link>

      <PosterPlaceholder item={item} variant="hero" className="mb-6" />

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span className={TIER_BADGE_CLASS[item.requiredTier]}>{TIER_LABELS[item.requiredTier]} Plan</span>
        <span className="flex items-center gap-1 text-sm font-semibold text-amber-400">
          <FiStar size={14} className="fill-current" /> {item.rating}
        </span>
      </div>

      <h1 className="section-heading">{item.title}</h1>
      <p className="mt-1 text-sm text-slate-400">{item.genre}</p>

      <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <dt className="flex items-center gap-1.5 text-xs text-slate-500">
            <FiCalendar size={13} /> Release Year
          </dt>
          <dd className="mt-1 font-medium text-white">{item.year}</dd>
        </div>
        <div>
          <dt className="flex items-center gap-1.5 text-xs text-slate-500">
            <FiClock size={13} /> {item.type === 'series' ? 'Seasons' : 'Duration'}
          </dt>
          <dd className="mt-1 font-medium text-white">
            {item.type === 'series' ? item.seasons : item.duration}
          </dd>
        </div>
        <div>
          <dt className="flex items-center gap-1.5 text-xs text-slate-500">
            <FiGlobe size={13} /> Language
          </dt>
          <dd className="mt-1 font-medium text-white">{item.language}</dd>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <dt className="flex items-center gap-1.5 text-xs text-slate-500">
            <FiUsers size={13} /> Cast
          </dt>
          <dd className="mt-1 font-medium text-white">{item.cast.slice(0, 2).join(', ')}</dd>
        </div>
      </dl>

      <p className="mt-5 max-w-2xl text-sm leading-relaxed text-slate-300">{item.description}</p>
      <p className="mt-3 text-xs text-slate-500">Full cast: {item.cast.join(', ')}</p>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          to={`/preview/${item.id}`}
          className="focus-ring btn-secondary"
          aria-label={`Preview ${item.title}`}
        >
          <FiPlay /> Preview
        </Link>

        {tierLoading ? (
          <span className="btn-primary pointer-events-none opacity-60">
            <Spinner size="sm" /> Checking access…
          </span>
        ) : canWatch ? (
          <Link to={`/watch/${item.id}`} className="focus-ring btn-primary">
            <FiPlay /> Watch Now
          </Link>
        ) : (
          <Link to="/plans" className="focus-ring btn-primary">
            <FiLock /> Upgrade Plan
          </Link>
        )}
      </div>

      {!tierLoading && !canWatch && (
        <p className="mt-3 text-sm text-slate-400">
          🔒 Premium Content — this title requires the {TIER_LABELS[item.requiredTier]} plan.
        </p>
      )}
    </div>
  );
}
