import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiUsers, FiEdit2, FiEye, FiSearch } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import Table, { TableRow, TableCell } from '../../components/common/Table';
import { SkeletonTableRows } from '../../components/common/Skeleton';
import Pagination from '../../components/common/Pagination';
import { EmptyState, ErrorState } from '../../components/common/EmptyState';
import CustomerEditModal from '../../components/admin/CustomerEditModal';
import { customerService } from '../../services/customerService';
import { formatDate } from '../../utils/formatters';

const PAGE_SIZE = 10;
const COLUMNS = ['Customer ID', 'Name', 'Email', 'Country', 'Phone', 'Joined', 'Actions'];

/**
 * Admin view of every customer on the platform. Uses the backend's
 * GET /customers?search=... (added to fix a confirmed bug: this page
 * used to request page_size=200 while searching, which the backend's
 * pagination validation caps at 100 -- every search deterministically
 * returned a 422, shown as "Try again"). Rows include a "View" link
 * to AdminCustomerDetailPage (/admin/customers/:id).
 */
export default function AdminCustomersPage() {
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [result, setResult] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingCustomer, setEditingCustomer] = useState(null);

  // Debounce: wait for a pause in typing before actually searching,
  // rather than firing a request on every keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await customerService.list({
        page,
        pageSize: PAGE_SIZE,
        search: search || undefined,
      });
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Failed to load customers.');
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Customers" subtitle="Every customer on the platform." />

      <div className="mb-6 flex items-center gap-3">
        <div className="relative max-w-sm flex-1">
          <FiSearch className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by name or email…"
            className="input-field pl-9"
            aria-label="Search customers by name or email"
          />
        </div>
        {!loading && !error && search && (
          <span className="text-sm text-slate-500">
            {result.total} {result.total === 1 ? 'result' : 'results'}
          </span>
        )}
      </div>

      {loading && (
        <Table columns={COLUMNS}>
          <SkeletonTableRows rows={PAGE_SIZE} columns={COLUMNS.length} />
        </Table>
      )}
      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && result.items.length === 0 && (
        <EmptyState
          icon={FiUsers}
          title={search ? `No customers match "${search}"` : 'No customers found'}
        />
      )}

      {!loading && !error && result.items.length > 0 && (
        <>
          <Table columns={COLUMNS}>
            {result.items.map((customer) => (
              <TableRow key={customer.id}>
                <TableCell className="font-mono text-xs text-slate-400" title={customer.id}>
                  CUS-{customer.id.slice(0, 8).toUpperCase()}
                </TableCell>
                <TableCell className="font-medium text-white">{customer.name}</TableCell>
                <TableCell>{customer.email}</TableCell>
                <TableCell>{customer.country}</TableCell>
                <TableCell>{customer.phone_number || '—'}</TableCell>
                <TableCell>{formatDate(customer.created_at)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Link
                      to={`/admin/customers/${customer.id}`}
                      className="focus-ring btn-ghost !p-2 text-slate-300 hover:text-white"
                      title={`View ${customer.name}`}
                      aria-label={`View ${customer.name}`}
                    >
                      <FiEye size={16} />
                    </Link>
                    <button
                      onClick={() => setEditingCustomer(customer)}
                      className="focus-ring btn-ghost !p-2"
                      title="Edit"
                      aria-label={`Edit ${customer.name}`}
                    >
                      <FiEdit2 size={16} />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} total={result.total} onPageChange={setPage} />
        </>
      )}

      <CustomerEditModal
        open={Boolean(editingCustomer)}
        onClose={() => setEditingCustomer(null)}
        customer={editingCustomer}
        onSaved={load}
      />
    </div>
  );
}
