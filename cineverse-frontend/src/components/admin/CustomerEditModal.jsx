import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import toast from 'react-hot-toast';
import { FiSave } from 'react-icons/fi';
import Modal from '../common/Modal';
import Spinner from '../common/Spinner';
import { customerService } from '../../services/customerService';
import { COUNTRIES } from '../../utils/constants';
import { extractErrorMessage } from '../../utils/formatters';

/**
 * Admin "Edit Customer" -- the one confirmed gap in the Customers CRUD
 * (Final Polish phase audit): the admin customers page was list-only,
 * with no way to edit a customer's details. Reuses the exact same
 * PATCH /customers/{id} endpoint and field set as the customer-facing
 * ProfilePage -- an admin editing someone else's record is allowed
 * server-side since Phase 1D's ownership enforcement grants admins
 * full access; nothing new needed on the backend.
 */
export default function CustomerEditModal({ open, onClose, customer, onSaved }) {
  const [submitting, setSubmitting] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm();

  useEffect(() => {
    if (open && customer) {
      reset({
        name: customer.name || '',
        phoneNumber: customer.phone_number || '',
        country: customer.country || 'US',
        address: customer.address || '',
      });
    }
  }, [open, customer, reset]);

  const onSubmit = async (values) => {
    setSubmitting(true);
    try {
      await customerService.update(customer.id, values);
      toast.success('Customer updated.');
      onSaved?.();
      onClose();
    } catch (err) {
      toast.error(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (!customer) return null;

  return (
    <Modal open={open} onClose={onClose} title={`Edit ${customer.name}`}>
      <p className="mb-4 text-xs text-slate-500">
        {customer.email} &middot; email can&apos;t be changed here.
      </p>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="label-text">Full name</label>
          <input className="input-field" {...register('name', { required: 'Name is required' })} />
          {errors.name && <p className="mt-1 text-xs text-red-400">{errors.name.message}</p>}
        </div>

        <div>
          <label className="label-text">Phone number</label>
          <input className="input-field" placeholder="+1 555 123 4567" {...register('phoneNumber')} />
        </div>

        <div>
          <label className="label-text">Country</label>
          <select className="input-field" {...register('country', { required: true })}>
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="label-text">Address</label>
          <textarea className="input-field resize-none" rows={2} {...register('address')} />
        </div>

        <div className="flex gap-3 pt-1">
          <button type="button" onClick={onClose} className="btn-secondary flex-1">
            Cancel
          </button>
          <button type="submit" disabled={submitting || !isDirty} className="btn-primary flex-1">
            {submitting ? (
              <Spinner size="sm" />
            ) : (
              <>
                <FiSave /> Save Changes
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
