import { Link } from 'react-router-dom';
import { FiFilm } from 'react-icons/fi';

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <FiFilm className="mb-4 text-[#E50914]" size={48} />
      <h1 className="text-4xl font-black text-white">404</h1>
      <p className="mt-2 text-slate-400">This scene doesn&apos;t exist.</p>
      <Link to="/" className="btn-primary mt-6">
        Back to CineVerse
      </Link>
    </div>
  );
}
