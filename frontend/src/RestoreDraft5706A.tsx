import { useState } from 'react';

type Props = {
  entryId: string;
  disabled: boolean;
  restore: (entryId: string, reason: string) => Promise<void>;
};

export default function RestoreDraft5706A({
  entryId, disabled, restore,
}: Props) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');

  async function confirmRestore() {
    if (disabled || working || !reason.trim()) return;

    if (!window.confirm(
      'Restore this earlier draft as a new save? ' +
      'The existing saved draft values will be replaced, ' +
      'but all historical records will be preserved.'
    )) return;

    setWorking(true);
    setError('');
    try {
      await restore(entryId, reason.trim());
      setOpen(false);
      setReason('');
    } catch (caught) {
      setError(caught instanceof Error
        ? caught.message
        : 'Restoration failed. Refresh and try again.');
    } finally {
      setWorking(false);
    }
  }

  return (
    <div style={{ marginTop: 12, padding: 12,
      border: '1px solid #D7E3E7', borderRadius: 6 }}>
      {!open ? (
        <button type="button" className="quiet"
          disabled={disabled || working}
          onClick={() => setOpen(true)}>
          Restore earlier draft
        </button>
      ) : (
        <div>
          <p>Restore these saved values as a new audited draft save.</p>
          <label>
            Reason for restoration
            <textarea aria-label="Reason for restoration"
              rows={3} maxLength={2000}
              value={reason} disabled={working}
              onChange={event => setReason(event.target.value)} />
          </label>
          <div className="actions">
            <button type="button"
              disabled={disabled || working || !reason.trim()}
              onClick={() => { void confirmRestore(); }}>
              {working ? 'Restoring...' : 'Confirm restoration'}
            </button>
            <button type="button" className="quiet"
              disabled={working}
              onClick={() => {
                setOpen(false);
                setReason('');
                setError('');
              }}>
              Cancel
            </button>
          </div>
          {disabled && <p role="status">
            Save or discard current changes before restoring.
          </p>}
          {error && <p role="alert" className="error">{error}</p>}
        </div>
      )}
    </div>
  );
}
