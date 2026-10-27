import { useParams, Link, Navigate } from 'react-router-dom';
import { FiArrowLeft, FiPlay } from 'react-icons/fi';
import { findCatalogItem } from '../data/catalogData';

/**
 * "Preview" no longer links out to YouTube or embeds any video --
 * it's a purely in-app placeholder, so no trailer content (copyrighted
 * or otherwise) is embedded or linked anywhere in this feature.
 */
export default function PreviewPage() {
  const { id } = useParams();
  const item = findCatalogItem(id);

  if (!item) {
    return <Navigate to="/movies" replace />;
  }

  const backHref = `/${item.type === 'series' ? 'series' : 'movies'}/${item.id}`;

  return (
    <div className="animate-fade-in mx-auto flex max-w-lg flex-col items-center py-16 text-center">
      <div className="icon-badge icon-badge-info mb-5 h-16 w-16">
        <FiPlay size={28} />
      </div>
      <h1 className="text-xl font-bold text-white">{item.title}</h1>
      <p className="mt-1 text-sm text-slate-500">Preview</p>
      <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
        This is a demonstration preview.
        <br />
        Actual media streaming is intentionally outside the scope of this Subscription Billing
        Platform.
      </p>
      <Link to={backHref} className="focus-ring btn-secondary mt-6 inline-flex items-center gap-2">
        <FiArrowLeft size={16} /> Back to Details
      </Link>
    </div>
  );
}
