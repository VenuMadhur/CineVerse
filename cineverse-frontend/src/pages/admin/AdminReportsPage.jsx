import { useState } from 'react';
import toast from 'react-hot-toast';
import { FiDownload, FiBarChart2 } from 'react-icons/fi';
import PageHeader from '../../components/common/PageHeader';
import SectionCard from '../../components/common/SectionCard';
import Spinner from '../../components/common/Spinner';
import {
  reportService,
  REPORT_TYPES_WITH_DATE_RANGE,
  CUSTOMER_INSIGHT_DIMENSIONS,
  OPERATIONAL_REPORT_DIMENSIONS,
} from '../../services/reportService';
import { downloadBlob } from '../../utils/download';
import { extractErrorMessage } from '../../utils/formatters';

const REPORT_TYPES = [
  { value: 'revenue', label: 'Revenue Report' },
  { value: 'customers', label: 'Customer Report' },
  { value: 'subscriptions', label: 'Subscription Report' },
  { value: 'payments', label: 'Payment Report' },
  { value: 'refunds', label: 'Refund Report' },
  { value: 'customer-insights', label: 'Customer Insights' },
  { value: 'operational', label: 'Operational Reports' },
];

const FORMATS = [
  { value: 'csv', label: 'CSV' },
  { value: 'xlsx', label: 'Excel (.xlsx)' },
  { value: 'pdf', label: 'PDF (summary)' },
];

/**
 * Admin Reports & Export (Phase 5). Every report reuses an existing
 * backend endpoint (GET /reports/{type}?format=&date_from=&date_to=) --
 * this page is purely a thin UI over reportService, mirroring the
 * download pattern already established for invoice PDFs (Phase 4).
 */
export default function AdminReportsPage() {
  const [reportType, setReportType] = useState('revenue');
  const [format, setFormat] = useState('csv');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [customerDimension, setCustomerDimension] = useState(CUSTOMER_INSIGHT_DIMENSIONS[0].value);
  const [operationalDimension, setOperationalDimension] = useState(
    OPERATIONAL_REPORT_DIMENSIONS[0].value
  );
  const [downloading, setDownloading] = useState(false);

  const supportsDateRange = REPORT_TYPES_WITH_DATE_RANGE.has(reportType);
  const isCustomerInsights = reportType === 'customer-insights';
  const isOperational = reportType === 'operational';
  const dimension = isCustomerInsights
    ? customerDimension
    : isOperational
      ? operationalDimension
      : undefined;

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const { blob, filename } = await reportService.download(reportType, {
        format,
        dateFrom: supportsDateRange ? dateFrom : undefined,
        dateTo: supportsDateRange ? dateTo : undefined,
        dimension,
      });
      downloadBlob(blob, filename);
      toast.success('Report downloaded.');
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Failed to generate the report.');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Reports"
        subtitle="Generate and export platform reports as CSV, Excel, or PDF."
      />

      <SectionCard icon={FiBarChart2} label="Export a Report" className="max-w-xl">
        <div className="space-y-4">
          <div>
            <label className="label-text">Report Type</label>
            <select
              className="input-field"
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
            >
              {REPORT_TYPES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {(isCustomerInsights || isOperational) && (
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              {isCustomerInsights && (
                <div>
                  <label className="label-text">Customer Insight</label>
                  <select
                    className="input-field"
                    value={customerDimension}
                    onChange={(e) => setCustomerDimension(e.target.value)}
                  >
                    {CUSTOMER_INSIGHT_DIMENSIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {isOperational && (
                <div>
                  <label className="label-text">Operational View</label>
                  <select
                    className="input-field"
                    value={operationalDimension}
                    onChange={(e) => setOperationalDimension(e.target.value)}
                  >
                    {OPERATIONAL_REPORT_DIMENSIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          <div className="border-t border-white/10 pt-4">
            <label className="label-text">Export Format</label>
            <select className="input-field" value={format} onChange={(e) => setFormat(e.target.value)}>
              {FORMATS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {format === 'pdf' && (
              <p className="mt-1 text-xs text-slate-500">
                PDF is a readable summary report (capped detail rows). Use CSV or Excel for the
                complete dataset.
              </p>
            )}
          </div>

          {supportsDateRange ? (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label-text">Date From (optional)</label>
                <input
                  type="date"
                  className="input-field"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </div>
              <div>
                <label className="label-text">Date To (optional)</label>
                <input
                  type="date"
                  className="input-field"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500">
              This report type doesn&apos;t support date-range filtering.
            </p>
          )}

          <button
            onClick={handleDownload}
            disabled={downloading}
            className="btn-primary w-full"
          >
            {downloading ? (
              <>
                <Spinner size="sm" /> Generating…
              </>
            ) : (
              <>
                <FiDownload /> Download Report
              </>
            )}
          </button>
        </div>
      </SectionCard>
    </div>
  );
}
