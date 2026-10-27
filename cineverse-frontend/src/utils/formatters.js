export function formatCurrency(amount, currency = 'USD') {
  const value = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (Number.isNaN(value)) return '—';
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}

/**
 * Formats a platform-wide aggregate (e.g. total revenue, MRR) that
 * the backend reports broken out by currency -- since Plan/Invoice/
 * Refund currency is genuinely unconstrained per-record, a single
 * blended number would silently misrepresent the total the moment
 * more than one currency is actually in use. Takes the same
 * `[{ currency, amount }]` shape GET /analytics/dashboard and
 * GET /analytics/refunds now return.
 *
 * - 0 entries -> the zero-amount display ("—" style, via formatCurrency)
 * - 1 entry   -> the normal single-currency display (unchanged from before)
 * - 2+ entries -> every currency shown explicitly, never merged
 */
export function formatCurrencyBreakdown(items) {
  if (!items || items.length === 0) return formatCurrency(0);
  if (items.length === 1) return formatCurrency(items[0].amount, items[0].currency);
  return items.map((item) => formatCurrency(item.amount, item.currency)).join(' + ');
}

export function formatDate(dateString) {
  if (!dateString) return '—';
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatDateTime(dateString) {
  if (!dateString) return '—';
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function titleCase(value) {
  if (!value) return '';
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function extractErrorMessage(error) {
  const detail = error?.response?.data?.error;
  // Field-level validation details (422s) are more specific and
  // actionable than the generic top-level message ("One or more
  // fields failed validation") -- check these first. Previously the
  // generic message was checked first, which meant this branch could
  // never actually be reached, since the backend's structured error
  // responses always include a top-level `message` too.
  if (Array.isArray(detail?.details) && detail.details.length > 0) {
    const first = detail.details[0];
    const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : null;
    if (first?.msg) return field ? `${field}: ${first.msg}` : first.msg;
  }
  if (detail?.message) return detail.message;
  // No response at all: either a network failure or a timeout, not a
  // structured backend error. axios's own message ("Network Error",
  // "timeout of 10000ms exceeded") is technically accurate but not
  // user-friendly -- give a clearer, actionable message instead.
  if (!error?.response) {
    if (error?.code === 'ECONNABORTED') {
      return 'The request took too long to respond. Please try again.';
    }
    return 'Unable to reach the server. Please check your connection and try again.';
  }
  if (error?.response?.status === 429) {
    return "You're doing that too quickly. Please wait a moment and try again.";
  }
  if (error?.response?.status >= 500) {
    return 'Something went wrong on our end. Please try again in a moment.';
  }
  if (error?.message) return error.message;
  return 'Something went wrong. Please try again.';
}
