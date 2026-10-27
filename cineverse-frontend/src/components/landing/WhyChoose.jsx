import { motion } from 'framer-motion';
import { FiCpu, FiShield, FiSmartphone, FiTrendingUp } from 'react-icons/fi';

const REASONS = [
  {
    icon: FiSmartphone,
    tone: 'icon-badge-brand',
    title: 'Watch Everywhere',
    description: 'Stream on your phone, tablet, laptop, or TV — pick up right where you left off.',
  },
  {
    icon: FiShield,
    tone: 'icon-badge-success',
    title: 'Secure Billing',
    description: 'JWT-secured accounts and a real subscription billing engine power every plan change.',
  },
  {
    icon: FiTrendingUp,
    tone: 'icon-badge-info',
    title: 'Flexible Plans',
    description: 'Upgrade or downgrade anytime — fair, prorated charges calculated automatically.',
  },
  {
    icon: FiCpu,
    tone: 'icon-badge-violet',
    title: 'Built to Scale',
    description: 'A production-grade backend handles invoicing, payments, and refunds under the hood.',
  },
];

export default function WhyChoose() {
  return (
    <section id="why" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <span className="mb-3 block text-center text-xs font-semibold uppercase tracking-wide text-[#ff4d54]">
        Why CineVerse
      </span>
      <h2 className="section-heading mb-10 text-center">Built for a better watch</h2>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {REASONS.map(({ icon: Icon, tone, title, description }, index) => (
          <motion.div
            key={title}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: index * 0.08 }}
            className="glass-card metric-card text-center"
          >
            <div className={`icon-badge ${tone} mx-auto mb-4 h-12 w-12`}>
              <Icon size={22} />
            </div>
            <h3 className="mb-2 font-bold text-white">{title}</h3>
            <p className="text-sm text-slate-400">{description}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
