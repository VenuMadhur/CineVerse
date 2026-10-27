import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiMenu, FiX } from 'react-icons/fi';
import { useAuth } from '../../hooks/useAuth';

export default function Navbar() {
  const { isAuthenticated, isSuperuser } = useAuth();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  // Bug fix: this previously always navigated to '/dashboard'
  // (customer) regardless of role. isSuperuser is already reliably
  // resolved by this point -- AuthContext resolves it via a
  // race-guarded effect keyed on the logged-in user, independent of
  // which page is currently mounted -- so no extra fetch or loading
  // state is needed here, just reading what's already available.
  const goToDashboard = () => navigate(isSuperuser ? '/admin/dashboard' : '/dashboard');

  return (
    <header className="fixed inset-x-0 top-0 z-40 bg-gradient-to-b from-black/80 to-transparent">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <Link to="/" className="focus-ring rounded-lg text-2xl font-black tracking-tight text-[#E50914]">
          CineVerse
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          <a href="#plans" className="focus-ring rounded-lg text-sm font-medium text-slate-200 hover:text-white">
            Plans
          </a>
          <a href="#why" className="focus-ring rounded-lg text-sm font-medium text-slate-200 hover:text-white">
            Why CineVerse
          </a>
          <a href="#faq" className="focus-ring rounded-lg text-sm font-medium text-slate-200 hover:text-white">
            FAQ
          </a>
        </div>

        <div className="hidden items-center gap-3 md:flex">
          {isAuthenticated ? (
            <button onClick={goToDashboard} className="btn-primary">
              {isSuperuser ? 'Admin Panel' : 'Go to Dashboard'}
            </button>
          ) : (
            <>
              <Link to="/login" className="btn-ghost">
                Sign In
              </Link>
              <Link to="/register" className="btn-primary">
                Get Started
              </Link>
            </>
          )}
        </div>

        <button
          className="focus-ring rounded-lg p-2 text-white md:hidden"
          onClick={() => setOpen((o) => !o)}
          aria-label="Toggle menu"
        >
          {open ? <FiX size={24} /> : <FiMenu size={24} />}
        </button>
      </nav>

      {open && (
        <div className="space-y-1 bg-[#0b1224] px-4 pb-4 md:hidden">
          <a href="#plans" className="block rounded-lg px-3 py-2 text-slate-200" onClick={() => setOpen(false)}>
            Plans
          </a>
          <a href="#why" className="block rounded-lg px-3 py-2 text-slate-200" onClick={() => setOpen(false)}>
            Why CineVerse
          </a>
          <a href="#faq" className="block rounded-lg px-3 py-2 text-slate-200" onClick={() => setOpen(false)}>
            FAQ
          </a>
          <div className="flex gap-2 pt-2">
            {isAuthenticated ? (
              <button onClick={goToDashboard} className="btn-primary w-full">
                {isSuperuser ? 'Admin Panel' : 'Dashboard'}
              </button>
            ) : (
              <>
                <Link to="/login" className="btn-secondary w-full text-center">
                  Sign In
                </Link>
                <Link to="/register" className="btn-primary w-full text-center">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
