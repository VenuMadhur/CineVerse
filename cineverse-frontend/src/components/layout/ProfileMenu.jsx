import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronDown, FiLogOut, FiUser } from 'react-icons/fi';
import { useAuth } from '../../hooks/useAuth';

/**
 * Step 14: replaces the previously non-interactive avatar with a real
 * dropdown. Only ever shows real account data (name/email from
 * AuthContext/CustomerContext) and links that genuinely exist --
 * `profileHref` is optional and simply omitted (not a dead link) when
 * the caller has nowhere real to send it. There's no "Settings" item
 * here: no such page exists anywhere in this app for either role, and
 * a menu entry that 404s isn't better than not having one.
 */
export default function ProfileMenu({ name, email, roleLabel, avatarIcon: AvatarIcon = FiUser, avatarClassName, profileHref }) {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="focus-ring flex items-center gap-3 rounded-lg p-1.5 pr-2 transition-colors hover:bg-white/[0.06]"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <div className="hidden text-right sm:block">
          <p className="text-sm font-semibold text-white">{name}</p>
          <p className="text-xs text-slate-500">{email}</p>
        </div>
        <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-white ${avatarClassName}`}>
          <AvatarIcon size={18} />
        </div>
        <FiChevronDown
          size={14}
          className={`hidden text-slate-500 transition-transform sm:block ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div
          role="menu"
          className="glass-card animate-scale-in absolute right-0 top-full z-50 mt-2 w-56 origin-top-right !rounded-xl p-2"
        >
          <div className="border-b border-white/10 px-3 py-2 sm:hidden">
            <p className="truncate text-sm font-semibold text-white">{name}</p>
            <p className="truncate text-xs text-slate-500">{email}</p>
          </div>
          {roleLabel && (
            <p className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              {roleLabel}
            </p>
          )}
          {profileHref && (
            <Link
              to={profileHref}
              onClick={() => setOpen(false)}
              role="menuitem"
              className="focus-ring flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-white"
            >
              <FiUser size={16} /> Profile
            </Link>
          )}
          <button
            onClick={() => {
              setOpen(false);
              logout();
            }}
            role="menuitem"
            className="focus-ring flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-red-400 transition-colors hover:bg-red-500/10"
          >
            <FiLogOut size={16} /> Logout
          </button>
        </div>
      )}
    </div>
  );
}
