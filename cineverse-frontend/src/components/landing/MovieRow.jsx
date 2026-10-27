import { motion } from 'framer-motion';
import { FiPlay, FiStar } from 'react-icons/fi';

/**
 * Public showcase row. Existing dimensions are intentionally preserved;
 * artwork is fitted into the same 44x64 / 52x72 card sizes.
 */
export default function MovieRow({ title, items }) {
  return (
    <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <h2 className="section-heading mb-5">{title}</h2>
      <div className="scrollbar-none flex gap-4 overflow-x-auto pb-4">
        {items.map((item, index) => (
          <motion.div
            key={item.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: index * 0.05 }}
            className="group relative h-64 w-44 flex-shrink-0 cursor-pointer overflow-hidden rounded-xl sm:h-72 sm:w-52"
          >
            {item.artwork?.poster ? (
              <img
                src={item.artwork.poster}
                alt={`${item.title} artwork`}
                loading="lazy"
                decoding="async"
                className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
              />
            ) : (
              <div className={`absolute inset-0 bg-gradient-to-br ${item.accent}`} />
            )}
            <div className="absolute inset-0 bg-black/20 transition-colors group-hover:bg-black/45" />
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent p-3 pt-10">
              <p className="line-clamp-2 text-sm font-bold text-white">{item.title}</p>
              <div className="mt-1 flex items-center gap-1 text-xs text-slate-300">
                <FiStar className="text-amber-400" size={12} />
                {item.rating} · {item.genre}
              </div>
            </div>
            <div className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100">
              <div className="rounded-full bg-white/90 p-3">
                <FiPlay className="text-black" size={20} />
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
