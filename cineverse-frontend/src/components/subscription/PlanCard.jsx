import { motion } from 'framer-motion';
import { FiCheck, FiStar } from 'react-icons/fi';
import { formatCurrency } from '../../utils/formatters';

export default function PlanCard({ plan, highlighted = false, badge, footer }) {
  const entitlements = plan.feature_entitlements || {};
  const featureEntries = Object.entries(entitlements);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4 }}
      className={`glass-card relative flex flex-col p-6 ${
        highlighted ? 'border-[#E50914]/50 ring-1 ring-[#E50914]/30' : ''
      }`}
    >
      {highlighted && (
        <span className="absolute -top-3 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-[#E50914] px-3 py-1 text-xs font-bold text-white">
          <FiStar size={12} /> Most Popular
        </span>
      )}
      {badge}

      <h3 className="text-xl font-bold text-white">{plan.name}</h3>
      {plan.description && <p className="mt-1 text-sm text-slate-400">{plan.description}</p>}

      <div className="my-5">
        <span className="text-4xl font-black text-white">
          {formatCurrency(plan.price, plan.currency)}
        </span>
        <span className="text-sm text-slate-400">
          /{plan.billing_interval === 'monthly' ? 'month' : 'year'}
        </span>
      </div>

      {plan.trial_period_days > 0 && (
        <p className="mb-4 text-xs font-semibold text-emerald-400">
          {plan.trial_period_days}-day free trial included
        </p>
      )}

      <ul className="mb-6 flex-1 space-y-2.5">
        {featureEntries.length > 0 ? (
          featureEntries.map(([key, value]) => (
            <li key={key} className="flex items-center gap-2 text-sm text-slate-300">
              <FiCheck className="flex-shrink-0 text-emerald-400" size={16} />
              <span className="capitalize">{key.replace(/_/g, ' ')}:</span>
              <span className="font-semibold text-white">{String(value)}</span>
            </li>
          ))
        ) : (
          <li className="text-sm text-slate-500">Standard CineVerse access</li>
        )}
      </ul>

      {footer}
    </motion.div>
  );
}
