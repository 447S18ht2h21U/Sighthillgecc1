import { useEffect, useState } from 'react';

type API = <T>(path: string, method?: string, data?: unknown) => Promise<T>;

type PaymentStatus = {
  fictional_acceptance_only: boolean;
  project_id: string;
  msr_id: string;
  approved_total: string;
  required_deposit: string;
  payment_ready: boolean;
  ceo_exception_valid: boolean;
  explanation: string;
  can_request: boolean;
  can_decide: boolean;
  operational_signature_verified: boolean;
  installation_authorized: boolean;
  exception: {
    id: string;
    status: string;
    request_reason: string;
    decision_reason: string;
    decided_at: string | null;
  } | null;
};

const projectId = 'f8a385b5-8e46-4c0c-886a-f8b6d2fc8d05';
const msrId = 'f555e52f-ae97-4342-982f-dbd42fb0fa62';
const endpoint = `fictional-payment-exceptions/${projectId}/`;

function verified(data: PaymentStatus) {
  if (data.fictional_acceptance_only !== true ||
      data.project_id !== projectId ||
      data.msr_id !== msrId ||
      data.operational_signature_verified !== false ||
      data.installation_authorized !== false) {
    throw new Error('Unexpected fictional payment exception response.');
  }
  return data;
}

export function FictionalPaymentException5928(
  {api, actorRole}: {api: API; actorRole: string}
) {
  const [data, setData] = useState<PaymentStatus | null>(null);
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setReason('');
    setConfirmed(false);
    setError('');
    setLoading(true);
    api<PaymentStatus>(endpoint).then(verified)
      .then(result => {
        if (!cancelled) setData(result);
      })
      .catch(err => {
        if (!cancelled) setError(String(err.message || err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [api, actorRole, reload]);

  async function submit(action: 'request' | 'decide', approve?: boolean) {
    if (!data || busy || !reason.trim()) return;
    if (action === 'request' && !data.can_request) return;
    if (action === 'decide' &&
        (actorRole !== 'CEO' || !data.can_decide ||
         !data.exception || !confirmed ||
         typeof approve !== 'boolean')) return;

    setBusy(true);
    setError('');
    try {
      const payload = action === 'request'
        ? {action, reason: reason.trim()}
        : {action, exception_id: data.exception!.id,
           approve, reason: reason.trim()};
      setData(verified(await api<PaymentStatus>(endpoint, 'POST', payload)));
      setReason('');
      setConfirmed(false);
    } catch (err) {
      setData(null);
      setConfirmed(false);
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  }

  const money = (value: string) =>
    Number(value).toLocaleString('en-US', {
      style: 'currency', currency: 'USD'
    });

  return <section className="veridian-guide-banner veridian-guide-banner--info">
    <h3>CEO Payment Exception</h3>
    <p><strong>Bob Jones - Project 105-SA-2026-11-23</strong></p>
    <p>FICTIONAL ACCEPTANCE TEST ONLY. No actual installation is authorized.</p>
    {loading && <p>Loading payment details...</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {data && <>
      <dl>
        <dt>Project total</dt><dd>{money(data.approved_total)}</dd>
        <dt>Payment terms</dt><dd>100% upon completion</dd>
        <dt>Deposit required</dt><dd>{money(data.required_deposit)}</dd>
        <dt>CEO payment exception</dt>
        <dd>{data.exception?.status === 'REQUESTED'
          ? 'Awaiting CEO approval'
          : data.exception?.status || 'Not requested'}</dd>
      </dl>
      <p role="status">{data.explanation}</p>
      {data.exception && <>
        <p>Request reason: {data.exception.request_reason}</p>
        {data.exception.decision_reason &&
          <p>Decision reason: {data.exception.decision_reason}</p>}
      </>}
      {(data.can_request || (actorRole === 'CEO' && data.can_decide)) && <>
        <label>{data.can_request ? 'Request reason' : 'Decision reason'}
          <textarea value={reason} maxLength={2000} disabled={busy}
            onChange={e => {setReason(e.target.value); setConfirmed(false);}}/>
        </label>
        {data.can_request && <button type="button"
          disabled={busy || !reason.trim()}
          onClick={() => void submit('request')}>
          Request CEO Payment Exception
        </button>}
        {actorRole === 'CEO' && data.can_decide && <>
          <label style={{display:'flex',gap:'0.5rem',alignItems:'center'}}>
            <input type="checkbox" checked={confirmed} disabled={busy}
              style={{width:'auto',margin:0}}
              onChange={e => setConfirmed(e.target.checked)}/>
            I reviewed the payment terms and confirm this decision is for fictional software acceptance only.
          </label>
          <div className="actions">
            <button type="button" disabled={busy || !confirmed || !reason.trim()}
              onClick={() => void submit('decide', true)}>
              Approve Payment Exception
            </button>
            <button type="button" className="quiet"
              disabled={busy || !confirmed || !reason.trim()}
              onClick={() => void submit('decide', false)}>
              Reject Payment Exception
            </button>
          </div>
        </>}
      </>}
      {data.payment_ready && data.ceo_exception_valid &&
        <p><strong>Payment exception requirement satisfied.</strong> Other installation requirements still apply.</p>}
    </>}
    <button type="button" className="quiet" disabled={busy || loading}
      onClick={() => setReload(value => value + 1)}>
      Refresh payment exception
    </button>
  </section>;
}