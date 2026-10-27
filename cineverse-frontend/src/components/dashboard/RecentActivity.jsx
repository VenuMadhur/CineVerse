import {
  FiActivity,
  FiUserPlus,
  FiFilm,
  FiPause,
  FiPlay,
  FiXCircle,
  FiRotateCcw,
  FiRepeat,
  FiFileText,
  FiCheckCircle,
  FiAlertTriangle,
  FiCreditCard,
  FiClock,
} from 'react-icons/fi';
import { formatDateTime, titleCase } from '../../utils/formatters';
import { EmptyState } from '../common/EmptyState';

// Verified against the real backend AuditEventType enum -- only maps
// event types that genuinely exist, not invented ones. Anything not
// listed here falls back to a neutral default (still real data, just
// a generic icon).
const EVENT_STYLES = {
  customer_created: { icon: FiUserPlus, tone: 'icon-badge-brand' },
  subscription_created: { icon: FiFilm, tone: 'icon-badge-brand' },
  trial_started: { icon: FiClock, tone: 'icon-badge-info' },
  trial_ended: { icon: FiClock, tone: 'icon-badge-warning' },
  subscription_plan_changed: { icon: FiRepeat, tone: 'icon-badge-violet' },
  subscription_paused: { icon: FiPause, tone: 'icon-badge-warning' },
  subscription_resumed: { icon: FiPlay, tone: 'icon-badge-success' },
  subscription_cancelled: { icon: FiXCircle, tone: 'icon-badge-warning' },
  subscription_cancellation_undone: { icon: FiRotateCcw, tone: 'icon-badge-info' },
  invoice_generated: { icon: FiFileText, tone: 'icon-badge-info' },
  invoice_paid: { icon: FiCheckCircle, tone: 'icon-badge-success' },
  invoice_failed: { icon: FiAlertTriangle, tone: 'icon-badge-warning' },
  payment_succeeded: { icon: FiCreditCard, tone: 'icon-badge-success' },
  payment_failed: { icon: FiAlertTriangle, tone: 'icon-badge-warning' },
  payment_refunded: { icon: FiRotateCcw, tone: 'icon-badge-warning' },
  refund_created: { icon: FiRotateCcw, tone: 'icon-badge-warning' },
};

const DEFAULT_STYLE = { icon: FiActivity, tone: 'bg-white/[0.06] text-slate-300' };

export default function RecentActivity({ events = [], limit = 8 }) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={FiActivity}
        title="No activity yet"
        description="Actions like subscribing, changing plans, or payments will show up here."
      />
    );
  }

  const shown = events.slice(0, limit);

  return (
    <ol className="relative">
      {shown.map((event, i) => {
        const { icon: Icon, tone } = EVENT_STYLES[event.event_type] || DEFAULT_STYLE;
        const isLast = i === shown.length - 1;
        return (
          <li key={event.id} className="relative flex gap-3 pb-6 last:pb-0">
            {!isLast && (
              <span
                aria-hidden="true"
                className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-white/10"
              />
            )}
            <div className={`icon-badge ${tone} z-10 h-8 w-8 flex-shrink-0`}>
              <Icon size={15} />
            </div>
            <div className="min-w-0 flex-1 pt-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-sm font-medium text-slate-200">{titleCase(event.event_type)}</p>
                <span className="flex-shrink-0 whitespace-nowrap text-xs text-slate-600">
                  {formatDateTime(event.created_at)}
                </span>
              </div>
              <p className="truncate text-xs text-slate-500">{event.description}</p>
              {event.remarks && (
                <p className="truncate text-xs italic text-slate-600">{event.remarks}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
