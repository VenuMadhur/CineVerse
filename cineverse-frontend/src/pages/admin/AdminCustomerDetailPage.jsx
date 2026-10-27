import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  FiUser,
  FiFilm,
  FiFileText,
  FiCreditCard,
  FiRotateCcw,
  FiActivity,
  FiEdit2,
  FiArrowLeft,
} from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import StatusBadge from '../../components/common/StatusBadge';
import { Skeleton } from '../../components/common/Skeleton';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import CustomerEditModal from '../../components/admin/CustomerEditModal';
import { customerService } from '../../services/customerService';
import { subscriptionService } from '../../services/subscriptionService';
import { planService } from '../../services/planService';
import { invoiceService } from '../../services/invoiceService';
import { paymentService } from '../../services/paymentService';
import { refundService } from '../../services/refundService';
import { auditLogService } from '../../services/auditLogService';
import { formatCurrency, formatDate, formatDateTime, titleCase } from '../../utils/formatters';

const TABS = [
  { key: 'profile', label: 'Profile', icon: FiUser },
  { key: 'subscriptions', label: 'Subscriptions', icon: FiFilm },
  { key: 'invoices', label: 'Invoices', icon: FiFileText },
  { key: 'payments', label: 'Payments', icon: FiCreditCard },
  { key: 'refunds', label: 'Refunds', icon: FiRotateCcw },
  { key: 'activity', label: 'Activity', icon: FiActivity },
];

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between border-b border-white/5 py-3 last:border-0">
      <span className="text-sm text-slate-400">{label}</span>
      <span className="ml-4 text-right text-sm font-medium text-white">{value || '—'}</span>
    </div>
  );
}

/**
 * Admin Customer Detail page — comprehensive view of a single customer.
 * Reaches /admin/customers/:customerId. All data comes from existing
 * endpoints: GET /customers/{id}, GET /subscriptions?customer_id=,
 * GET /invoices?customer_id=, GET /payments?customer_id=,
 * GET /refunds?customer_id=, GET /audit-logs/customer/{id}.
 * No new backend endpoints were created.
 */
export default function AdminCustomerDetailPage() {
  const { customerId } = useParams();
  const [activeTab, setActiveTab] = useState('profile');
  const [customer, setCustomer] = useState(null);
  const [customerLoading, setCustomerLoading] = useState(true);
  const [customerError, setCustomerError] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  // Plan names for the Subscriptions tab: fetched once (not per-row)
  // alongside that tab's data -- see the loaders object below. Plans
  // are a small, bounded reference set, unlike customers/
  // subscriptions, so this stays a single extra request rather than
  // N+1.
  const [planNameById, setPlanNameById] = useState(new Map());

  // Per-tab data
  const [tabData, setTabData] = useState({});
  const [tabLoading, setTabLoading] = useState({});
  const [tabError, setTabError] = useState({});

  // Load customer profile
  useEffect(() => {
    setCustomerLoading(true);
    customerService
      .get(customerId)
      .then(setCustomer)
      .catch(() => setCustomerError('Failed to load customer.'))
      .finally(() => setCustomerLoading(false));
  }, [customerId]);

  // Load tab data on first visit to that tab. Uses a ref (not
  // tabData/tabLoading themselves) to decide whether a fetch is
  // already in flight or done -- depending on state this same effect
  // sets would re-trigger the effect on every one of its own updates
  // (a new object reference each time), causing 2-3 needless extra
  // runs per tab per visit.
  const loadedTabsRef = useRef({});
  useEffect(() => {
    if (loadedTabsRef.current[activeTab]) return;
    loadedTabsRef.current[activeTab] = true;

    setTabLoading((p) => ({ ...p, [activeTab]: true }));

    const loaders = {
      subscriptions: () =>
        Promise.all([
          subscriptionService.list({ customerId, pageSize: 50 }),
          planService.list({ pageSize: 100 }),
        ]).then(([subsResult, plansResult]) => {
          setPlanNameById(new Map(plansResult.items.map((p) => [p.id, p.name])));
          return subsResult.items;
        }),
      invoices: () =>
        invoiceService.list({ customerId, pageSize: 50 }).then((d) => d.items),
      payments: () =>
        paymentService.list({ customerId, pageSize: 50 }).then((d) => d.items),
      refunds: () =>
        refundService.list({ customerId, pageSize: 50 }).then((d) => d.items),
      activity: () =>
        auditLogService.listForEntity('customer', customerId).then((d) => d.items ?? d),
    };

    const loader = loaders[activeTab];
    if (!loader) {
      setTabLoading((p) => ({ ...p, [activeTab]: false }));
      return;
    }

    loader()
      .then((items) => setTabData((p) => ({ ...p, [activeTab]: items })))
      .catch(() => {
        loadedTabsRef.current[activeTab] = false; // allow retrying this tab
        setTabError((p) => ({ ...p, [activeTab]: `Failed to load ${activeTab}.` }));
      })
      .finally(() => setTabLoading((p) => ({ ...p, [activeTab]: false })));
  }, [activeTab, customerId]);

  // A different customerId (e.g. navigating straight from one
  // customer's detail page to another) must not show the previous
  // customer's already-loaded tab data.
  useEffect(() => {
    loadedTabsRef.current = {};
    setTabData({});
    setTabLoading({});
    setTabError({});
  }, [customerId]);

  const isTabLoading = tabLoading[activeTab];
  const isTabError = tabError[activeTab];
  const tabItems = tabData[activeTab] ?? [];

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <Link
          to="/admin/customers"
          className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
        >
          <FiArrowLeft size={14} /> Back to Customers
        </Link>
      </div>

      {customerLoading && (
        <div className="space-y-3">
          <Skeleton className="h-8 w-64 rounded" />
          <Skeleton className="h-4 w-48 rounded" />
        </div>
      )}
      {customerError && !customerLoading && <ErrorState message={customerError} />}

      {!customerLoading && !customerError && customer && (
        <>
          <PageHeader
            title={customer.name}
            subtitle={`${customer.email} · ${customer.country}`}
            actions={
              <button
                onClick={() => setEditOpen(true)}
                className="btn-secondary"
              >
                <FiEdit2 size={15} /> Edit Customer
              </button>
            }
          />

          {/* Tab Bar */}
          <div className="mb-6 flex gap-1 overflow-x-auto border-b border-white/10 pb-0">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`focus-ring inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === key
                    ? 'border-[#E50914] text-white'
                    : 'border-transparent text-slate-400 hover:text-white'
                }`}
              >
                <Icon size={15} />
                {label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="glass-card p-6">
            {/* ── Profile ── */}
            {activeTab === 'profile' && (
              <div className="max-w-lg">
                <InfoRow label="Customer ID" value={<span className="font-mono text-xs">{customer.id}</span>} />
                <InfoRow label="Full Name" value={customer.name} />
                <InfoRow label="Email" value={customer.email} />
                <InfoRow label="Country" value={customer.country} />
                <InfoRow label="State" value={customer.state} />
                <InfoRow label="Phone" value={customer.phone_number} />
                <InfoRow label="Address" value={customer.address} />
                <InfoRow label="Member Since" value={formatDate(customer.created_at)} />
                <InfoRow label="Last Updated" value={formatDateTime(customer.updated_at)} />
              </div>
            )}

            {/* ── Loading / Error states for other tabs ── */}
            {activeTab !== 'profile' && isTabLoading && (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 rounded-lg" />
                ))}
              </div>
            )}
            {activeTab !== 'profile' && isTabError && !isTabLoading && (
              <ErrorState message={isTabError} />
            )}

            {/* ── Subscriptions ── */}
            {activeTab === 'subscriptions' && !isTabLoading && !isTabError && (
              <>
                {tabItems.length === 0 ? (
                  <EmptyState icon={FiFilm} title="No subscriptions" />
                ) : (
                  <div className="divide-y divide-white/5">
                    {tabItems.map((sub) => (
                      <div key={sub.id} className="flex items-center justify-between py-4">
                        <div>
                          <p className="font-mono text-xs text-slate-400">{sub.id.slice(0, 12)}…</p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            Plan: <span className="font-medium text-slate-200">{planNameById.get(sub.plan_id) || sub.plan_id.slice(0, 8)}</span>
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="text-right text-xs text-slate-400">
                            <p>Created: {formatDate(sub.created_at)}</p>
                            {sub.activated_at && <p>Activated: {formatDate(sub.activated_at)}</p>}
                          </div>
                          <StatusBadge status={sub.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* ── Invoices ── */}
            {activeTab === 'invoices' && !isTabLoading && !isTabError && (
              <>
                {tabItems.length === 0 ? (
                  <EmptyState icon={FiFileText} title="No invoices" />
                ) : (
                  <div className="divide-y divide-white/5">
                    {tabItems.map((inv) => (
                      <div key={inv.id} className="flex items-center justify-between py-4">
                        <div>
                          <p className="font-medium text-white">{inv.invoice_number}</p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            Due: {formatDate(inv.due_date)}
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <p className="text-sm font-semibold text-white">
                            {formatCurrency(inv.total_amount, inv.currency)}
                          </p>
                          <StatusBadge status={inv.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* ── Payments ── */}
            {activeTab === 'payments' && !isTabLoading && !isTabError && (
              <>
                {tabItems.length === 0 ? (
                  <EmptyState icon={FiCreditCard} title="No payments" />
                ) : (
                  <div className="divide-y divide-white/5">
                    {tabItems.map((p) => (
                      <div key={p.id} className="flex items-center justify-between py-4">
                        <div>
                          <p className="font-mono text-xs text-white">
                            {p.gateway_reference || p.id.slice(0, 12)}
                          </p>
                          <p className="mt-0.5 text-xs capitalize text-slate-500">
                            {p.payment_method?.replace(/_/g, ' ')} · attempt #{p.attempt_number}
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <p className="text-sm font-semibold text-white">
                            {formatCurrency(p.amount, p.currency)}
                          </p>
                          <StatusBadge status={p.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* ── Refunds ── */}
            {activeTab === 'refunds' && !isTabLoading && !isTabError && (
              <>
                {tabItems.length === 0 ? (
                  <EmptyState icon={FiRotateCcw} title="No refunds" />
                ) : (
                  <div className="divide-y divide-white/5">
                    {tabItems.map((r) => (
                      <div key={r.id} className="flex items-center justify-between py-4">
                        <div>
                          <p className="text-sm text-white">{r.reason}</p>
                          <p className="mt-0.5 text-xs text-slate-500">
                            {formatDate(r.created_at)}
                          </p>
                        </div>
                        <div className="flex items-center gap-4">
                          <p className="text-sm font-semibold text-sky-400">
                            {formatCurrency(r.amount, r.currency)}
                          </p>
                          <StatusBadge status={r.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* ── Activity ── */}
            {activeTab === 'activity' && !isTabLoading && !isTabError && (
              <>
                {tabItems.length === 0 ? (
                  <EmptyState icon={FiActivity} title="No activity recorded" />
                ) : (
                  <div className="divide-y divide-white/5">
                    {tabItems.map((event) => (
                      <div key={event.id} className="py-3">
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="text-sm font-medium text-white">
                              {titleCase(event.event_type)}
                            </p>
                            <p className="mt-0.5 text-xs text-slate-400">{event.description}</p>
                          </div>
                          <p className="ml-4 shrink-0 text-xs text-slate-500">
                            {formatDateTime(event.created_at)}
                          </p>
                        </div>
                        {(event.old_value || event.new_value) && (
                          <p className="mt-1 text-xs text-slate-500">
                            {event.old_value && <span>was: {event.old_value}</span>}
                            {event.old_value && event.new_value && ' → '}
                            {event.new_value && <span>now: {event.new_value}</span>}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <CustomerEditModal
            open={editOpen}
            onClose={() => setEditOpen(false)}
            customer={customer}
            onSaved={() => customerService.get(customerId).then(setCustomer)}
          />
        </>
      )}
    </div>
  );
}
