import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import Modal from '../../components/common/Modal';
import retryService from '../../services/retryService';

export default function RetryFormModal({ open, onClose, config, onSaved }) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({
    defaultValues: {
      retry_attempt: 1,
      retry_after_days: 1,
      is_active: true,
    },
  });

  useEffect(() => {
    if (open) {
      if (config) {
        reset({
          retry_attempt: config.retry_attempt,
          retry_after_days: config.retry_after_days,
          is_active: config.is_active,
        });
      } else {
        reset({
          retry_attempt: 1,
          retry_after_days: 1,
          is_active: true,
        });
      }
    }
  }, [open, config, reset]);

  const onSubmit = async (data) => {
    try {
      if (config) {
        // Only retry_after_days and is_active are updatable according to backend schema
        await retryService.updateConfiguration(config.id, {
          retry_after_days: parseInt(data.retry_after_days, 10),
          is_active: data.is_active,
        });
        toast.success(`Attempt ${config.retry_attempt} updated.`);
      } else {
        await retryService.createConfiguration({
          retry_attempt: parseInt(data.retry_attempt, 10),
          retry_after_days: parseInt(data.retry_after_days, 10),
          is_active: data.is_active,
        });
        toast.success('Retry configuration created.');
      }
      onSaved();
      onClose();
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Failed to save configuration.');
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={config ? `Edit Attempt ${config.retry_attempt}` : 'New Retry Configuration'}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {!config && (
          <div>
            <label className="block text-sm font-medium text-slate-300">Attempt Number</label>
            <input
              type="number"
              min="1"
              {...register('retry_attempt', { required: 'Attempt number is required', min: 1 })}
              className="input-field mt-1 w-full"
            />
            {errors.retry_attempt && (
              <p className="mt-1 text-sm text-red-400">{errors.retry_attempt.message}</p>
            )}
          </div>
        )}
        
        {config && (
          <div>
            <label className="block text-sm font-medium text-slate-300">Attempt Number</label>
            <input
              type="number"
              disabled
              value={config.retry_attempt}
              className="input-field mt-1 w-full opacity-50 cursor-not-allowed"
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-slate-300">Days After Failure</label>
          <input
            type="number"
            min="1"
            {...register('retry_after_days', { required: 'Days after failure is required', min: 1 })}
            className="input-field mt-1 w-full"
          />
          {errors.retry_after_days && (
            <p className="mt-1 text-sm text-red-400">{errors.retry_after_days.message}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_active"
            {...register('is_active')}
            className="h-4 w-4 rounded border-white/10 bg-white/5 text-amber-500 focus:ring-amber-500 focus:ring-offset-slate-900"
          />
          <label htmlFor="is_active" className="text-sm font-medium text-slate-300">
            Active
          </label>
        </div>

        <div className="flex justify-end gap-3 pt-4">
          <button type="button" onClick={onClose} className="btn-secondary" disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
