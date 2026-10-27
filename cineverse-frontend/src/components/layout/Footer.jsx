import { FiFacebook, FiInstagram, FiTwitter, FiYoutube } from 'react-icons/fi';

export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#0b1224] px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div>
            <h4 className="mb-3 text-sm font-semibold text-slate-300">Company</h4>
            <ul className="space-y-2 text-sm text-slate-500">
              <li>About Us</li>
              <li>Careers</li>
              <li>Press</li>
            </ul>
          </div>
          <div>
            <h4 className="mb-3 text-sm font-semibold text-slate-300">Support</h4>
            <ul className="space-y-2 text-sm text-slate-500">
              <li>Help Center</li>
              <li>Contact Us</li>
              <li>Device Support</li>
            </ul>
          </div>
          <div>
            <h4 className="mb-3 text-sm font-semibold text-slate-300">Legal</h4>
            <ul className="space-y-2 text-sm text-slate-500">
              <li>Terms of Use</li>
              <li>Privacy Policy</li>
              <li>Cookie Preferences</li>
            </ul>
          </div>
          <div>
            <h4 className="mb-3 text-sm font-semibold text-slate-300">Follow Us</h4>
            <div className="flex gap-3 text-slate-500">
              <FiFacebook size={20} />
              <FiTwitter size={20} />
              <FiInstagram size={20} />
              <FiYoutube size={20} />
            </div>
          </div>
        </div>
        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-6 sm:flex-row">
          <p className="text-sm font-black text-[#E50914]">CineVerse</p>
          <p className="text-xs text-slate-600">
            &copy; {new Date().getFullYear()} CineVerse. Demo product for a subscription billing
            platform — not affiliated with any real streaming service.
          </p>
        </div>
      </div>
    </footer>
  );
}
