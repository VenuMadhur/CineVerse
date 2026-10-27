import { Link } from 'react-router-dom';
import { FiArrowRight, FiFilm } from 'react-icons/fi';
import Hero from '../components/landing/Hero';
import MovieRow from '../components/landing/MovieRow';
import WhyChoose from '../components/landing/WhyChoose';
import FAQ from '../components/landing/FAQ';
import Footer from '../components/layout/Footer';
import PlanCard from '../components/subscription/PlanCard';
import Spinner from '../components/common/Spinner';
import { ErrorState, EmptyState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { planService } from '../services/planService';
import { MOVIES, SERIES } from '../data/catalogData';

export default function LandingPage() {
  const {
    data: plansResult,
    loading,
    error,
    refetch,
  } = useApi(() => planService.list({ status: 'active' }), []);

  const plans = plansResult?.items || [];

  return (
    <div>
      <Hero />

      {/* Public showcase only -- browsable without any subscription.
          No tier badges, no watch/preview actions here; MovieRow
          already renders exactly "artwork, title, rating, genre" with
          no interactivity, which is precisely what's wanted for an
          unauthenticated showcase. Real detail/watch pages live behind
          login on /movies and /series. */}
      <MovieRow title="🎬 Trending Movies" items={MOVIES} />
      <MovieRow title="📺 Popular Web Series" items={SERIES} />

      <section id="plans" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <h2 className="section-heading mb-2 text-center">Choose Your Plan</h2>
        <p className="mb-10 text-center text-slate-400">
          Simple, transparent pricing. Upgrade or downgrade anytime.
        </p>

        {loading && (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        )}
        {error && !loading && <ErrorState message={error} onRetry={refetch} />}
        {!loading && !error && plans.length === 0 && (
          <EmptyState icon={FiFilm} title="No plans are available right now" description="Check back soon." />
        )}

        {!loading && !error && plans.length > 0 && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {plans.map((plan, index) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                highlighted={index === Math.floor(plans.length / 2)}
                footer={
                  <Link to="/register" className="btn-primary w-full">
                    Subscribe <FiArrowRight />
                  </Link>
                }
              />
            ))}
          </div>
        )}
      </section>

      <WhyChoose />
      <FAQ />
      <Footer />
    </div>
  );
}
