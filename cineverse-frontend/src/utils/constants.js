// Central place for environment-driven and app-wide constants.
// Never hardcode the API URL anywhere else in the codebase.
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'cv_access_token',
  REFRESH_TOKEN: 'cv_refresh_token',
};

// ISO 3166-1 alpha-2 countries the backend has configured tax rates for,
// plus a broader common list for the registration/profile forms. The
// backend (TaxService) falls back to a 0% default for any country not
// explicitly configured, so any valid code is safe to submit.
export const COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'IN', name: 'India' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'AE', name: 'United Arab Emirates' },
  { code: 'SG', name: 'Singapore' },
  { code: 'JP', name: 'Japan' },
  { code: 'BR', name: 'Brazil' },
  { code: 'ZA', name: 'South Africa' },
];

export const SUBSCRIPTION_STATUS_LABELS = {
  trial: 'Trial',
  active: 'Active',
  past_due: 'Past Due',
  paused: 'Paused',
  cancelled: 'Cancelled',
};

export const INVOICE_STATUS_LABELS = {
  draft: 'Draft',
  open: 'Open',
  paid: 'Paid',
  failed: 'Failed',
  void: 'Void',
  refunded: 'Refunded',
};

export const PAYMENT_STATUS_LABELS = {
  pending: 'Pending',
  succeeded: 'Succeeded',
  failed: 'Failed',
  refunded: 'Refunded',
};

export const REFUND_STATUS_LABELS = {
  pending: 'Pending',
  completed: 'Completed',
  failed: 'Failed',
};
