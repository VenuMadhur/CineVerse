import { FiChevronLeft, FiChevronRight } from 'react-icons/fi';

export default function Pagination({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  return (
    <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
      <span>
        Page {page} of {totalPages} &middot; {total} total
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="btn-ghost !px-3 !py-1.5 disabled:opacity-30"
        >
          <FiChevronLeft /> Prev
        </button>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="btn-ghost !px-3 !py-1.5 disabled:opacity-30"
        >
          Next <FiChevronRight />
        </button>
      </div>
    </div>
  );
}
