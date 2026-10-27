import { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { FiTag, FiPlus, FiArchive, FiRotateCcw, FiTrash2, FiEdit2 } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import FilterChips from '../../components/common/FilterChips';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import StatusBadge from '../../components/common/StatusBadge';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import PlanFormModal from '../../components/admin/PlanFormModal';
import { planService } from '../../services/planService';
import { formatCurrency, extractErrorMessage } from '../../utils/formatters';

const COLUMNS = ['Name', 'Price', 'Interval', 'Trial Days', 'Status', 'Actions'];

const ACTION_CONFIG = {
  archive: {
    label: 'Archive',
    confirmLabel: 'Archive',
    variant: 'danger',
    title: 'Archive plan?',
    message: (plan) =>
      `Archive "${plan.name}"? Existing subscribers keep using it -- it just won't be offered to new customers.`,
    run: (planId) => planService.archive(planId),
    successMessage: (plan) => `${plan.name} archived.`,
  },
  unarchive: {
    label: 'Unarchive',
    confirmLabel: 'Unarchive',
    variant: 'primary',
    title: 'Unarchive plan?',
    message: (plan) => `Make "${plan.name}" available to new customers again?`,
    run: (planId) => planService.unarchive(planId),
    successMessage: (plan) => `${plan.name} unarchived.`,
  },
  delete: {
    label: 'Delete',
    confirmLabel: 'Delete Permanently',
    variant: 'danger',
    title: 'Delete plan?',
    message: (plan) =>
      `Permanently delete "${plan.name}"? This cannot be undone. Only possible if no customer has ever subscribed to it.`,
    run: (planId) => planService.remove(planId),
    successMessage: (plan) => `${plan.name} deleted.`,
  },
};

/**
 * Admin management of Plans: list (existing GET /plans, already
 * public), create/update/archive/unarchive/delete (admin-only).
 * Archive/Create/Update/List existed before this pass; Unarchive and
 * Delete are new, following the exact same service/router pattern.
 */
export default function AdminPlansPage() {
  const [statusFilter, setStatusFilter] = useState('');
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null); // { plan, type: 'archive'|'unarchive'|'delete' }
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await planService.list({ status: statusFilter || undefined, pageSize: 100 });
      setPlans(data.items);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load plans.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConfirmAction = async () => {
    if (!confirmAction) return;
    const config = ACTION_CONFIG[confirmAction.type];
    setActionLoading(true);
    setActionError(null);
    try {
      await config.run(confirmAction.plan.id);
      toast.success(config.successMessage(confirmAction.plan));
      setConfirmAction(null);
      load();
    } catch (err) {
      // Delete is the one action that can be legitimately blocked
      // (e.g. the plan has subscription history) -- show the
      // backend's specific reason right in the dialog rather than
      // just a generic toast, so the admin understands why.
      setActionError(extractErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Plans"
        subtitle="Create, edit, archive, and manage subscription plans."
        actions={
          <button
            onClick={() => {
              setEditingPlan(null);
              setFormOpen(true);
            }}
            className="btn-primary"
          >
            <FiPlus /> New Plan
          </button>
        }
      />

      <FilterChips
        options={['', 'active', 'archived']}
        value={statusFilter}
        onChange={setStatusFilter}
      />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={5} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && plans.length === 0 && (
        <EmptyState icon={FiTag} title="No plans yet" description="Create your first plan to get started." />
      )}

      {!loading && !error && plans.length > 0 && (
        <Table columns={COLUMNS}>
          {plans.map((plan) => {
            const isArchived = plan.status === 'archived';
            return (
              <TableRow key={plan.id}>
                <TableCell className="font-medium text-white">
                  <div className="flex items-center gap-2">
                    {plan.name}
                    {isArchived && (
                      <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                        Archived
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell>{formatCurrency(plan.price, plan.currency)}</TableCell>
                <TableCell className="capitalize">{plan.billing_interval}</TableCell>
                <TableCell>{plan.trial_period_days}</TableCell>
                <TableCell>
                  <StatusBadge status={plan.status} />
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <button
                      onClick={() => {
                        setEditingPlan(plan);
                        setFormOpen(true);
                      }}
                      className="focus-ring btn-ghost !p-2"
                      title="Edit"
                      aria-label={`Edit ${plan.name}`}
                    >
                      <FiEdit2 size={16} />
                    </button>
                    {isArchived ? (
                      <button
                        onClick={() => setConfirmAction({ plan, type: 'unarchive' })}
                        className="focus-ring btn-ghost !p-2 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300"
                        title="Unarchive"
                        aria-label={`Unarchive ${plan.name}`}
                      >
                        <FiRotateCcw size={16} />
                      </button>
                    ) : (
                      <button
                        onClick={() => setConfirmAction({ plan, type: 'archive' })}
                        className="focus-ring btn-ghost !p-2 text-amber-400 hover:bg-amber-500/10 hover:text-amber-300"
                        title="Archive"
                        aria-label={`Archive ${plan.name}`}
                      >
                        <FiArchive size={16} />
                      </button>
                    )}
                    <button
                      onClick={() => setConfirmAction({ plan, type: 'delete' })}
                      className="focus-ring btn-ghost !p-2 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                      title="Delete"
                      aria-label={`Delete ${plan.name}`}
                    >
                      <FiTrash2 size={16} />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </Table>
      )}

      <PlanFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        plan={editingPlan}
        onSaved={load}
      />

      <ConfirmDialog
        open={Boolean(confirmAction)}
        onClose={() => {
          setConfirmAction(null);
          setActionError(null);
        }}
        onConfirm={handleConfirmAction}
        loading={actionLoading}
        variant={confirmAction ? ACTION_CONFIG[confirmAction.type].variant : 'danger'}
        title={confirmAction ? ACTION_CONFIG[confirmAction.type].title : ''}
        message={
          actionError ||
          (confirmAction ? ACTION_CONFIG[confirmAction.type].message(confirmAction.plan) : '')
        }
        confirmLabel={confirmAction ? ACTION_CONFIG[confirmAction.type].confirmLabel : 'Confirm'}
      />
    </div>
  );
}
