import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiChevronDown } from 'react-icons/fi';

const FAQS = [
  {
    q: 'Can I change plans later?',
    a: 'Yes. Upgrade or downgrade anytime from your dashboard. If you\'re mid-billing-cycle, we calculate a fair prorated charge or credit automatically — no manual math required.',
  },
  {
    q: 'How does billing work?',
    a: 'Your plan renews automatically each billing cycle. You can view every invoice, payment, and refund from your account at any time.',
  },
  {
    q: 'Can I cancel anytime?',
    a: 'Yes — cancel immediately or at the end of your current billing cycle, whichever you prefer.',
  },
  {
    q: 'Is my payment information secure?',
    a: 'All billing operations run through a dedicated, JWT-secured billing engine designed around real-world payment processing patterns.',
  },
];

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState(0);

  return (
    <section id="faq" className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8">
      <h2 className="section-heading mb-10 text-center">Frequently Asked Questions</h2>
      <div className="space-y-3">
        {FAQS.map((item, index) => {
          const isOpen = openIndex === index;
          return (
            <div key={item.q} className="glass-card overflow-hidden">
              <button
                onClick={() => setOpenIndex(isOpen ? -1 : index)}
                className="flex w-full items-center justify-between px-5 py-4 text-left"
              >
                <span className="font-semibold text-white">{item.q}</span>
                <FiChevronDown
                  className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
              </button>
              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <p className="px-5 pb-4 text-sm text-slate-400">{item.a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </section>
  );
}
