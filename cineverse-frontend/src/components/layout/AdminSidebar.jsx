import { NavLink, Link } from 'react-router-dom';
import {
  FiGrid,
  FiUsers,
  FiTag,
  FiFilm,
  FiFileText,
  FiCreditCard,
  FiRotateCcw,
  FiBarChart2,
  FiTrendingUp,
  FiActivity,
  FiLogOut,
  FiSettings,
} from 'react-icons/fi';
import { useAuth } from '../../hooks/useAuth';

const NAV_ITEMS = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: FiGrid },
  { to: '/admin/customers', label: 'Customers', icon: FiUsers },
  { to: '/admin/plans', label: 'Plans', icon: FiTag },
  { to: '/admin/subscriptions', label: 'Subscriptions', icon: FiFilm },
  { to: '/admin/invoices', label: 'Invoices', icon: FiFileText },
  { to: '/admin/payments', label: 'Payments', icon: FiCreditCard },
  { to: '/admin/refunds', label: 'Refunds', icon: FiRotateCcw },
  { to: '/admin/analytics', label: 'Analytics', icon: FiTrendingUp },
  { to: '/admin/reports', label: 'Reports', icon: FiBarChart2 },
  { to: '/admin/audit-log', label: 'Audit Log', icon: FiActivity },
  { to: '/admin/retry-config', label: 'Retry Config', icon: FiSettings },
];

export default function AdminSidebar({ onNavigate }) {
  const { logout } = useAuth();

  return (
    <aside className="flex h-full w-64 flex-col border-r border-white/10 bg-[#0b1224]/95 backdrop-blur-xl">
      <Link to="/" onClick={onNavigate} className="focus-ring flex items-center gap-2 rounded-lg px-6 py-6">
        <span className="text-2xl font-black tracking-tight text-white">CineVerse</span>
        <span className="rounded-full border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-amber-400">
          Admin
        </span>
      </Link>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            // end prop prevents /admin/customers matching /admin/customers/:id
            end={to === '/admin/customers'}
            className={({ isActive }) =>
              `focus-ring flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-amber-500/15 text-white shadow-[inset_2px_0_0_0_#f59e0b]'
                  : 'text-slate-400 hover:bg-white/[0.06] hover:text-white'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
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
