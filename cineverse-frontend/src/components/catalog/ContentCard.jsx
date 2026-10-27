import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FiPlay, FiStar } from 'react-icons/fi';
import PosterPlaceholder from './PosterPlaceholder';

/**
 * A single catalog card for the authenticated /movies and /series
 * grids. The required subscription tier is deliberately NOT shown
 * here -- browsing should feel open; the tier badge only appears on
 * the detail page, at the point the customer actually considers
 * watching. The whole card links to the detail page (keyboard-
 * navigable via the existing focus-ring convention); "Preview" is a
 * separate, nested in-app link (no external link, no embedded video
 * anywhere) so it doesn't trigger the card's own navigation.
 */
export default function ContentCard({ item, index = 0 }) {
  const detailHref = `/${item.type === 'series' ? 'series' : 'movies'}/${item.id}`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.35, delay: Math.min(index, 8) * 0.05 }}
      className="glass-card metric-card group relative flex flex-col overflow-hidden !p-3"
    >
      <Link
        to={detailHref}
        className="focus-ring rounded-lg"
        aria-label={`View details for ${item.title}`}
      >
        <PosterPlaceholder
          item={item}
          className="transition-transform duration-300 group-hover:scale-[1.03]"
        />
      </Link>

      <div className="mt-3 flex-1">
        <Link to={detailHref} className="focus-ring rounded">
          <h3 className="line-clamp-1 font-bold text-white">{item.title}</h3>
        </Link>
        <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
          <span className="flex items-center gap-1 text-amber-400">
            <FiStar size={12} className="fill-current" /> {item.rating}
          </span>
          <span aria-hidden="true">&middot;</span>
          <span className="truncate">{item.genre}</span>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          {item.type === 'series' ? `${item.seasons} Season${item.seasons > 1 ? 's' : ''}` : item.duration}
        </p>
      </div>

      <div className="mt-3 flex items-center justify-end">
        <Link
          to={`/preview/${item.id}`}
          className="focus-ring btn-ghost !p-1.5 text-xs text-slate-300 hover:text-white"
          aria-label={`Preview ${item.title}`}
        >
          <FiPlay size={13} /> Preview
        </Link>
      </div>
    </motion.div>
  );
}
