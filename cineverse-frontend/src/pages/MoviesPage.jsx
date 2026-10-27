import PageHeader from '../components/common/PageHeader';
import ContentCard from '../components/catalog/ContentCard';
import { MOVIES } from '../data/catalogData';

/**
 * Static demo catalog -- no backend requests. Responsive grid:
 * 1 col mobile, 2 cols tablet, 3-4 cols desktop.
 */
export default function MoviesPage() {
  return (
    <div className="animate-fade-in">
      <PageHeader
        title="🎬 Trending Movies"
        subtitle="A demo catalog showing how subscription tiers unlock premium content."
      />
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {MOVIES.map((movie, i) => (
          <ContentCard key={movie.id} item={movie} index={i} />
        ))}
      </div>
    </div>
  );
}
