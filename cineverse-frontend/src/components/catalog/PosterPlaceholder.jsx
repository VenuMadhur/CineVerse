import { useState } from 'react';
import { FiFilm, FiTv } from 'react-icons/fi';

/**
 * Artwork renderer for the existing catalog containers.
 * The container dimensions/aspect ratios are intentionally unchanged.
 * Different artwork variants are selected for portrait cards vs. wide hero areas.
 */
export default function PosterPlaceholder({ item, className = '', variant = 'card' }) {
  const [failed, setFailed] = useState(false);
  const Icon = item.type === 'series' ? FiTv : FiFilm;
  const isHero = variant === 'hero';
  const imageSrc = isHero
    ? item.artwork?.hero || item.artwork?.landscape || item.artwork?.poster
    : item.artwork?.poster;

  return (
    <div
      className={`relative overflow-hidden rounded-xl bg-gradient-to-br ${item.accent} ${
        isHero ? 'aspect-[21/9] sm:aspect-[3/1]' : 'aspect-[2/3]'
      } ${className}`}
    >
      {imageSrc && !failed ? (
        <img
          src={imageSrc}
          alt={`${item.title} artwork`}
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className={`absolute inset-0 h-full w-full object-cover ${
            isHero ? 'object-center' : 'object-center'
          }`}
        />
      ) : (
        <>
          <div className="absolute inset-0 bg-gradient-to-br from-slate-800 via-slate-900 to-black" />
          <Icon className="absolute inset-0 m-auto text-white/20" size={isHero ? 72 : 56} aria-hidden="true" />
        </>
      )}

      <div className="absolute inset-0 bg-black/15" />
      <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent" />
      <span
        className={`absolute z-10 font-bold leading-tight text-white drop-shadow ${
          isHero ? 'inset-x-6 bottom-5 text-left text-2xl sm:text-3xl' : 'inset-x-3 bottom-3 text-sm'
        }`}
      >
        {item.title}
      </span>
    </div>
  );
}
