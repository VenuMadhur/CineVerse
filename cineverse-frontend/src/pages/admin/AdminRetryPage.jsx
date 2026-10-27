import { useCallback, useEffect, useState } from 'react';
import { FiSettings, FiPlus, FiEdit2 } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import StatusBadge from '../../components/common/StatusBadge';
import RetryFormModal from '../../components/admin/RetryFormModal';
import retryService from '../../services/retryService';

const COLUMNS = ['Attempt', 'Days After Failure', 'Status', 'Actions'];

export default function AdminRetryPage() {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await retryService.getConfigurations(0, 100);
      setConfigs(data.items);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load retry configurations.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Retry Configuration"
        subtitle="Manage the automated payment retry schedule for past-due subscriptions."
        actions={
          <button
            onClick={() => {
              setEditingConfig(null);
              setFormOpen(true);
            }}
            className="btn-primary"
          >
            <FiPlus /> New Rule
          </button>
        }
      />

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={3} columns={COLUMNS.length} />
        </Table>
      )}
      
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && configs.length === 0 && (
        <EmptyState icon={FiSettings} title="No retry schedule" description="Configure retry rules to automatically recover failed payments." />
      )}

      {!loading && !error && configs.length > 0 && (
        <Table columns={COLUMNS}>
          {configs.map((config) => (
            <TableRow key={config.id}>
              <TableCell className="font-medium text-white">
                Attempt {config.retry_attempt}
              </TableCell>
              <TableCell>{config.retry_after_days} {config.retry_after_days === 1 ? 'day' : 'days'}</TableCell>
              <TableCell>
                <StatusBadge status={config.is_active ? 'active' : 'inactive'} />
              </TableCell>
              <TableCell>
                <button
                  onClick={() => {
                    setEditingConfig(config);
                    setFormOpen(true);
                  }}
                  className="focus-ring btn-ghost !p-2"
                  title="Edit"
                  aria-label={`Edit Attempt ${config.retry_attempt}`}
                >
                  <FiEdit2 size={16} />
                </button>
              </TableCell>
            </TableRow>
          ))}
        </Table>
      )}

      <RetryFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        config={editingConfig}
        onSaved={load}
      />
    </div>
  );
}
