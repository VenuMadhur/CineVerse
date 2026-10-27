import { FiMenu, FiShield } from 'react-icons/fi';
import { useAuth } from '../../hooks/useAuth';
import ProfileMenu from './ProfileMenu';

export default function AdminTopbar({ onMenuClick }) {
  const { accountInfo } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-[#0F172A]/80 px-4 backdrop-blur-xl sm:px-6">
      <button
        onClick={onMenuClick}
        className="rounded-lg p-2 text-slate-300 hover:bg-white/10 lg:hidden"
        aria-label="Open menu"
      >
        <FiMenu size={22} />
      </button>

      <div className="hidden lg:block" />

      <ProfileMenu
        name={accountInfo?.fullName || 'Admin'}
        email={accountInfo?.email}
        roleLabel="Administrator"
        avatarIcon={FiShield}
        avatarClassName="bg-gradient-to-br from-amber-500 to-amber-700"
      />
    </header>
  );
}
