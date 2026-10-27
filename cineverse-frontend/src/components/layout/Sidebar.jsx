import { NavLink, Link } from 'react-router-dom';
import {
  FiFilm,
  FiTv,
  FiGrid,
  FiTag,
  FiRepeat,
  FiFileText,
  FiCreditCard,
  FiRotateCcw,
  FiUser,
  FiActivity,
  FiLogOut,
  FiShield,
} from 'react-icons/fi';
import { useAuth } from '../../hooks/useAuth';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: FiGrid },
  { to: '/plans', label: 'Plans', icon: FiTag },
  { to: '/movies', label: 'Movies', icon: FiFilm },
  { to: '/series', label: 'Web Series', icon: FiTv },
  { to: '/subscriptions', label: 'Subscriptions', icon: FiRepeat },
  { to: '/invoices', label: 'Invoices', icon: FiFileText },
  { to: '/payments', label: 'Payments', icon: FiCreditCard },
  { to: '/refunds', label: 'Refunds', icon: FiRotateCcw },
  { to: '/profile', label: 'Profile', icon: FiUser },
  { to: '/activity', label: 'Activity', icon: FiActivity },
];

export default function Sidebar({ onNavigate }) {
  const { logout, isSuperuser } = useAuth();

  return (
    <aside className="flex h-full w-64 flex-col border-r border-white/10 bg-[#0b1224]/95 backdrop-blur-xl">
      <Link to="/" onClick={onNavigate} className="focus-ring flex items-center gap-2 rounded-lg px-6 py-6">
        <span className="text-2xl font-black tracking-tight text-[#E50914]">CineVerse</span>
      </Link>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              `focus-ring flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-[#E50914]/15 text-white shadow-[inset_2px_0_0_0_#E50914]'
                  : 'text-slate-400 hover:bg-white/[0.06] hover:text-white'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}

        {isSuperuser && (
          <Link
            to="/admin/dashboard"
            onClick={onNavigate}
            className="focus-ring mt-2 flex items-center gap-3 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-4 py-2.5 text-sm font-medium text-amber-400 transition-colors hover:bg-amber-500/[0.12]"
          >
            <FiShield size={18} />
            Admin Panel
          </Link>
        )}
      </nav>

      <div className="border-t border-white/10 p-3">
        <button
          onClick={logout}
          className="focus-ring flex w-full items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-red-500/10 hover:text-red-400"
        >
          <FiLogOut size={18} />
          Logout
        </button>
      </div>
    </aside>
  );
}
