import PageHeader from '../components/common/PageHeader';
import ContentCard from '../components/catalog/ContentCard';
import { SERIES } from '../data/catalogData';

/**
 * Static demo catalog -- no backend requests. Responsive grid:
 * 1 col mobile, 2 cols tablet, 3-4 cols desktop.
 */
export default function SeriesPage() {
  return (
    <div className="animate-fade-in">
      <PageHeader
        title="📺 Popular Web Series"
        subtitle="A demo catalog showing how subscription tiers unlock premium content."
      />
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {SERIES.map((series, i) => (
          <ContentCard key={series.id} item={series} index={i} />
        ))}
      </div>
    </div>
  );
}
