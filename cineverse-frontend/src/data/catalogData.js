/**
 * Static, presentational demo catalog only -- CineVerse's backend is a
 * subscription billing engine, not a real content/streaming catalog.
 * Nothing here is fetched from any API; this exists purely to
 * demonstrate how a subscription tier would unlock content.
 *
 * Titles, genres, cast, and release years are factual, publicly-known
 * information (the same kind of data any film-database or listings
 * site references). Descriptions are original, brief summaries in
 * our own words, not reproduced marketing copy. No poster artwork is
 * fetched or embedded anywhere in this feature -- each card renders
 * an original, brand-styled placeholder (see PosterPlaceholder.jsx)
 * using artwork URLs from TMDB's image CDN. The UI never changes its
 * existing container dimensions; each artwork variant adapts to the
 * location where it is rendered. No trailer video or
 * external link is embedded or hardcoded anywhere -- "Preview" opens
 * an in-app placeholder page (see PreviewPage.jsx) explaining that
 * this is a demonstration, not a real trailer.
 *
 * requiredTier matches the mapping given for this feature exactly:
 * starter | professional | premium.
 */

export const MOVIES = [
  {
    id: 'avengers-endgame',
    type: 'movie',
    title: 'Avengers: Endgame',
    year: 2019,
    genre: 'Action, Adventure, Sci-Fi',
    rating: '8.4',
    duration: '3h 1m',
    language: 'English',
    cast: ['Robert Downey Jr.', 'Chris Evans', 'Scarlett Johansson', 'Chris Hemsworth'],
    description:
      "The surviving Avengers assemble one final time to undo a universe-altering catastrophe, in the epic conclusion to over a decade of interconnected superhero storytelling.",
    requiredTier: 'premium',
    accent: 'from-red-600 to-slate-900',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/7RyHsO4yDXtBv1zUU3mTpHeQ0d5.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/7RyHsO4yDXtBv1zUU3mTpHeQ0d5.jpg',
    },  },
  {
    id: 'interstellar',
    type: 'movie',
    title: 'Interstellar',
    year: 2014,
    genre: 'Adventure, Drama, Sci-Fi',
    rating: '8.7',
    duration: '2h 49m',
    language: 'English',
    cast: ['Matthew McConaughey', 'Anne Hathaway', 'Jessica Chastain'],
    description:
      'A team of explorers travels through a wormhole in search of a new home for humanity, racing against time and the limits of relativity itself.',
    requiredTier: 'professional',
    accent: 'from-indigo-700 to-slate-900',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/rAiYTfKGqDCRIIqo664sY9XZIvQ.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/rAiYTfKGqDCRIIqo664sY9XZIvQ.jpg',
    },  },
  {
    id: 'fight-club',
    type: 'movie',
    title: 'Fight Club',
    year: 1999,
    genre: 'Drama',
    rating: '8.8',
    duration: '2h 19m',
    language: 'English',
    cast: ['Brad Pitt', 'Edward Norton', 'Helena Bonham Carter'],
    description:
      'An insomniac office worker and a soap salesman build an underground fight club that spirals into something far more dangerous and anarchic.',
    requiredTier: 'starter',
    accent: 'from-slate-700 to-black',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/hZkgoQYus5vegHoetLkCJzb17zJ.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/hZkgoQYus5vegHoetLkCJzb17zJ.jpg',
    },  },
  {
    id: 'se7en',
    type: 'movie',
    title: 'Se7en',
    year: 1995,
    genre: 'Crime, Drama, Thriller',
    rating: '8.6',
    duration: '2h 7m',
    language: 'English',
    cast: ['Brad Pitt', 'Morgan Freeman', 'Gwyneth Paltrow'],
    description:
      'Two detectives hunt a serial killer who uses the seven deadly sins as his motive in a series of meticulously staged murders.',
    requiredTier: 'professional',
    accent: 'from-amber-900 to-black',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/6yoghtyTpznpBik8EngEmJskVUO.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/cHAiNdPbQXbGLp0D8xPbL8MvMSr.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/cHAiNdPbQXbGLp0D8xPbL8MvMSr.jpg',
    },  },
  {
    id: 'spiderman-across-the-spiderverse',
    type: 'movie',
    title: 'Spider-Man: Across the Spider-Verse',
    year: 2023,
    genre: 'Animation, Action, Adventure',
    rating: '8.6',
    duration: '2h 20m',
    language: 'English',
    cast: ['Shameik Moore', 'Hailee Steinfeld', 'Oscar Isaac'],
    description:
      'Miles Morales journeys across a multiverse of Spider-People, confronting a new threat that puts everything he loves at risk.',
    requiredTier: 'professional',
    accent: 'from-fuchsia-700 to-indigo-900',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/2I5eBh98Q4aPq8WdQrHdTC8ARhY.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/2I5eBh98Q4aPq8WdQrHdTC8ARhY.jpg',
    },  },
  {
    id: '3-idiots',
    type: 'movie',
    title: '3 Idiots',
    year: 2009,
    genre: 'Comedy, Drama',
    rating: '8.4',
    duration: '2h 50m',
    language: 'Hindi',
    cast: ['Aamir Khan', 'R. Madhavan', 'Sharman Joshi'],
    description:
      'Two friends go in search of their long-lost college companion, unraveling memories of a rebellious, free-thinking engineering student who upended their conventional lives.',
    requiredTier: 'starter',
    accent: 'from-yellow-600 to-orange-800',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/66A9MqXOyVFCssoloscw79z8Tew.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/8gT3UKtglLVpu0YfccwbmXZ5Eis.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/8gT3UKtglLVpu0YfccwbmXZ5Eis.jpg',
    },  },
];

export const SERIES = [
  {
    id: 'breaking-bad',
    type: 'series',
    title: 'Breaking Bad',
    year: 2008,
    genre: 'Crime, Drama, Thriller',
    rating: '9.5',
    seasons: 5,
    language: 'English',
    cast: ['Bryan Cranston', 'Aaron Paul', 'Anna Gunn'],
    description:
      'A high school chemistry teacher turned methamphetamine manufacturer descends deeper into the criminal underworld to secure his family\u2019s future.',
    requiredTier: 'professional',
    accent: 'from-emerald-700 to-slate-900',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/anFx9aTOOYqgS3v7x3R84Kz67ly.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/tsRy63Mu5cu8etL1X7ZLyf7UP1M.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/tsRy63Mu5cu8etL1X7ZLyf7UP1M.jpg',
    },  },
  {
    id: 'the-mentalist',
    type: 'series',
    title: 'The Mentalist',
    year: 2008,
    genre: 'Crime, Drama, Mystery',
    rating: '8.1',
    seasons: 7,
    language: 'English',
    cast: ['Simon Baker', 'Robin Tunney', 'Tim Kang'],
    description:
      'A former celebrity psychic medium turned consultant uses his sharp observational skills to help the California Bureau of Investigation solve murders.',
    requiredTier: 'starter',
    accent: 'from-sky-700 to-slate-900',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/acYXu4KaDj1NIkMgObnhe4C4a0T.jpg',
      landscape: 'https://image.tmdb.org/t/p/w500/acYXu4KaDj1NIkMgObnhe4C4a0T.jpg',
      hero: 'https://image.tmdb.org/t/p/w500/acYXu4KaDj1NIkMgObnhe4C4a0T.jpg',
    },  },
  {
    id: 'game-of-thrones',
    type: 'series',
    title: 'Game of Thrones',
    year: 2011,
    genre: 'Action, Adventure, Drama',
    rating: '9.2',
    seasons: 8,
    language: 'English',
    cast: ['Emilia Clarke', 'Kit Harington', 'Peter Dinklage'],
    description:
      'Noble families vie for control of the Iron Throne while an ancient threat awakens beyond a great wall of ice in the north.',
    requiredTier: 'premium',
    accent: 'from-slate-600 to-black',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/u3bZgnGQ9T01sWNhyveQz0wH0Hl.jpg',
      landscape: 'https://image.tmdb.org/t/p/w500/u3bZgnGQ9T01sWNhyveQz0wH0Hl.jpg',
      hero: 'https://image.tmdb.org/t/p/w500/u3bZgnGQ9T01sWNhyveQz0wH0Hl.jpg',
    },  },
  {
    id: 'mouse',
    type: 'series',
    title: 'Mouse',
    year: 2021,
    genre: 'Crime, Mystery, Thriller',
    rating: '8.7',
    seasons: 1,
    language: 'Korean',
    cast: ['Lee Seung-gi', 'Lee Hee-joon', 'Park Ju-hyun'],
    description:
      'A rookie police officer is drawn into a psychologically twisted hunt for a serial killer, questioning what truly separates a predator from everyone else.',
    requiredTier: 'premium',
    accent: 'from-red-800 to-black',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/lrWHBK1h4rrEnx5Ml8iDR1SwNux.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/4Fj8sRNtqcMPR2H2zpXQ1rHrlGz.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/4Fj8sRNtqcMPR2H2zpXQ1rHrlGz.jpg',
    },  },
  {
    id: 'dark',
    type: 'series',
    title: 'Dark',
    year: 2017,
    genre: 'Crime, Drama, Mystery',
    rating: '8.8',
    seasons: 3,
    language: 'German',
    cast: ['Louis Hofmann', 'Karoline Eichhorn', 'Lisa Vicari'],
    description:
      'The disappearance of children in a small German town uncovers a family saga that spans generations and bends time itself.',
    requiredTier: 'professional',
    accent: 'from-slate-800 to-black',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/apbrbWs8M9lyOpJYU5WXrpFbk1Z.jpg',
      landscape: 'https://image.tmdb.org/t/p/w500/apbrbWs8M9lyOpJYU5WXrpFbk1Z.jpg',
      hero: 'https://image.tmdb.org/t/p/w500/apbrbWs8M9lyOpJYU5WXrpFbk1Z.jpg',
    },  },
  {
    id: 'peaky-blinders',
    type: 'series',
    title: 'Peaky Blinders',
    year: 2013,
    genre: 'Crime, Drama',
    rating: '8.8',
    seasons: 6,
    language: 'English',
    cast: ['Cillian Murphy', 'Paul Anderson', 'Sophie Rundle'],
    description:
      'A fiercely ambitious gangster family fights to rise above their post-war Birmingham origins and expand their criminal empire.',
    requiredTier: 'premium',
    accent: 'from-neutral-700 to-black',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/vUUqzWa2LnHIVqkaKVlVGkVcZIW.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/or7wKwv1IT6LEOktt395O5qi7e.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/or7wKwv1IT6LEOktt395O5qi7e.jpg',
    },  },
  {
    id: 'squid-game',
    type: 'series',
    title: 'Squid Game',
    year: 2021,
    genre: 'Action, Drama, Mystery',
    rating: '8.0',
    seasons: 2,
    language: 'Korean',
    cast: ['Lee Jung-jae', 'Park Hae-soo', 'Wi Ha-jun'],
    description:
      'Hundreds of cash-strapped contestants compete in deadly children\u2019s games for a life-changing cash prize, with far higher stakes than any of them expect.',
    requiredTier: 'professional',
    accent: 'from-pink-700 to-slate-900',

    artwork: {
      poster: 'https://image.tmdb.org/t/p/w500/dDlEmu3EZ0Pgg93K2SVNLCjCSvE.jpg',
      landscape: 'https://image.tmdb.org/t/p/w1280/oaGvjB0DvdhXhOAuADfHb261ZHa.jpg',
      hero: 'https://image.tmdb.org/t/p/w1280/oaGvjB0DvdhXhOAuADfHb261ZHa.jpg',
    },  },
];

export const CATALOG = [...MOVIES, ...SERIES];

export const TIER_LABELS = {
  starter: 'Starter',
  professional: 'Professional',
  premium: 'Premium',
};

/** Higher-tier subscribers can access everything lower tiers can. */
export const TIER_RANK = { starter: 1, professional: 2, premium: 3 };

export function findCatalogItem(id) {
  return CATALOG.find((item) => item.id === id) || null;
}
