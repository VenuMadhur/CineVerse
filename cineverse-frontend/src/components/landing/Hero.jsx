import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { FiPlay, FiInfo } from 'react-icons/fi';

export default function Hero() {
  return (
    <section className="relative flex min-h-[92vh] items-end overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-[#3a0a0f] via-[#1a1030] to-[#0F172A]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_70%_20%,rgba(229,9,20,0.35),transparent)]" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#0F172A] via-transparent to-transparent" />

      <div className="relative z-10 mx-auto w-full max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="max-w-2xl"
        >
          <span className="mb-4 inline-block rounded-full bg-[#E50914]/15 px-3 py-1 text-xs font-semibold tracking-wide text-[#ff4d54] uppercase">
            Now Streaming Worldwide
          </span>
          <h1 className="text-4xl font-black leading-tight text-white sm:text-5xl lg:text-6xl">
            Unlimited movies, shows &amp; more.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-slate-300">
            One subscription. Every screen. Cancel anytime — powered by a real, production-grade
            billing engine underneath the scenes.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link to="/register" className="btn-primary px-6 py-3 text-base">
              <FiPlay /> Get Started
            </Link>
            <a href="#plans" className="btn-secondary px-6 py-3 text-base">
              <FiInfo /> View Plans
            </a>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
