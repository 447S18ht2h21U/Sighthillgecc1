import { useEffect, useState } from 'react';

type API = <T>(path: string, method?: string, data?: unknown) => Promise<T>;
type Project = { id: string; code: string; customer_name: string };
type Page<T> = { results: T[]; next: string | null };
type Payment = {
  id: string; project: string; msr: string; kind: string;
  amount: string; received_date: string; payment_reference: string;
  status: string; bank_confirmed: boolean; confirmation_date: string | null;
};
type Feedback = { kind: 'working' | 'success' | 'error'; text: string };

export function CustomerPayments4716({
  api, onBack, selectedProjectId,
}: {
  api: API;
  onBack: () => void;
  selectedProjectId?: string;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(selectedProjectId ?? '');
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [action, setAction] = useState('');
  const [revision, setRevision] = useState(0);
  const [kind, setKind] = useState('DEPOSIT');
  const [amount, setAmount] = useState('');
  const [receivedDate, setReceivedDate] = useState('');
  const [reference, setReference] = useState('');

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const all: Project[] = [];
        let page = 1;
        while (true) {
          const result = await api<Page<Project>>(
            `operational-projects/?page=${page}`
          );
          all.push(...result.results);
          if (!result.next) break;
          page++;
        }
        if (active) setProjects(all);
      } catch (error) {
        if (active) setFeedback({
          kind: 'error', text: (error as Error).message,
        });
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    let active = true;
    if (!projectId) {
      setPayments([]);
      return () => { active = false; };
    }
    void api<Payment[]>(
      `customer-payments/?project=${encodeURIComponent(projectId)}`
    ).then(result => {
      if (active) setPayments(result);
    }).catch(error => {
      if (active) {
        setPayments([]);
        setFeedback({
          kind: 'error',
          text: `Could not load payments: ${(error as Error).message}`,
        });
      }
    });
    return () => { active = false; };
  }, [api, projectId, revision]);

  async function execute(
    operation: () => Promise<unknown>, success: string
  ) {
    if (busy) return;
    setBusy(true);
    setFeedback({
      kind: 'working',
      text: 'Processing and recording audit evidence...',
    });
    try {
      await operation();
      setFeedback({ kind: 'success', text: success });
      setAction('');
      setRevision(value => value + 1);
    } catch (error) {
      setFeedback({
        kind: 'error', text: (error as Error).message,
      });
    } finally {
      setBusy(false);
    }
  }

  function feedbackFor(target: string) {
    if (!feedback || action !== target) return null;
    return <p className={`customer-payment-feedback ${feedback.kind}`}
      role={feedback.kind === 'error' ? 'alert' : 'status'}>
      {feedback.text}
    </p>;
  }

  return <section className="customer-payments-workspace">
    <div className="customer-payment-actions">
      <button type="button" className="quiet" onClick={onBack}>
        Return to Customers &amp; Projects
      </button>
    </div>
    <h2>Customer Payment Evidence</h2>
    <p>
      Record the payment, verify its supporting evidence, then separately
      confirm bank availability. All three operations are audited.
    </p>
    <p className="muted">
      Comptroller only. This screen records employee attestations;
      it does not retrieve or verify bank transactions automatically.
    </p>

    <label>Project
      <select value={projectId} disabled={busy || loading}
        onChange={event => {
          setProjectId(event.target.value);
          setAction('');
          setPayments([]);
          setFeedback(null);
        }}>
        <option value="">
          {loading ? 'Loading projects...' : 'Choose project'}
        </option>
        {projects.map(project =>
          <option key={project.id} value={project.id}>
            {project.code} — {project.customer_name}
          </option>
        )}
      </select>
    </label>

    {projectId && <>
      <form onSubmit={event => {
        event.preventDefault();
        setAction('record');
        void execute(async () => {
          await api('customer-payments/', 'POST', {
            project: projectId, kind, amount,
            received_date: receivedDate,
            payment_reference: reference.trim(),
          });
          setAmount('');
          setReceivedDate('');
          setReference('');
        }, 'Payment recorded as Pending Verification. Bank availability is not confirmed.');
      }}>
        <h3>1. Record Customer Payment</h3>
        <div className="grid">
          <label>Payment type
            <select disabled={busy} value={kind}
              onChange={event => setKind(event.target.value)}>
              <option value="DEPOSIT">Deposit</option>
              <option value="FINAL">Final payment</option>
              <option value="FULL">Full payment</option>
            </select>
          </label>
          <label>Amount ($)
            <input required type="number" min="0.01" step="0.01"
              disabled={busy} value={amount}
              onChange={event => setAmount(event.target.value)}/>
          </label>
          <label>Date received
            <input required type="date" disabled={busy}
              value={receivedDate}
              onChange={event => setReceivedDate(event.target.value)}/>
          </label>
          <label>Payment reference
            <input required maxLength={150} disabled={busy}
              value={reference}
              onChange={event => setReference(event.target.value)}/>
          </label>
        </div>
        <label className="customer-payment-confirm">
          <input required type="checkbox" key={projectId + reference}/>
          I reviewed the payment information. This records an unverified
          payment only.
        </label>
        <button disabled={busy}>Record Pending Payment</button>
        {feedbackFor('record')}
      </form>

      <div className="customer-payment-actions">
        <h3>2. Review Payments</h3>
        <button type="button" className="quiet" disabled={busy}
          onClick={() => {
            setRevision(value => value + 1);
            setFeedback({
              kind: 'working', text: 'Refreshing payment records...',
            });
          }}>
          Refresh payment records
        </button>
      </div>

      {payments.length === 0 &&
        <p>No customer payments are recorded for this project.</p>}

      {payments.some(payment => payments.some(other =>
        other.id !== payment.id &&
        other.payment_reference === payment.payment_reference
      )) && <p role="alert" className="customer-payment-feedback error">
        Duplicate payment references were found for this project.
        These records require controlled review before bank availability
        can be confirmed. Do not treat them as separate deposits.
      </p>}

      {payments.map(payment =>
        <div className="customer-payment-entry" key={payment.id}>
          <p><strong>
            {payment.kind.replaceAll('_', ' ')} — ${payment.amount}
          </strong></p>
          <p>
            Reference: {payment.payment_reference}
            {' | '}Received: {payment.received_date}
          </p>
          <p>
            Payment: <strong>{payment.status.replaceAll('_', ' ')}</strong>
            {' | '}Bank availability: <strong>
              {payment.bank_confirmed
                ? `Confirmed ${payment.confirmation_date ?? ''}`
                : 'Not confirmed'}
            </strong>
          </p>

          {payment.status === 'PENDING' &&
            !payments.some(other =>
              other.id !== payment.id &&
              other.payment_reference === payment.payment_reference
            ) && <>
            <button type="button" className="quiet" disabled={busy}
              onClick={() => {
                setAction(action === `verify-${payment.id}`
                  ? '' : `verify-${payment.id}`);
                setFeedback(null);
              }}>
              Review for Verification
            </button>
            {action === `verify-${payment.id}` &&
              <form onSubmit={event => {
                event.preventDefault();
                void execute(
                  () => api(
                    `customer-payments/${payment.id}/verify/`,
                    'POST', {}
                  ),
                  'Payment verified. Bank availability remains unconfirmed.'
                );
              }}>
                <p>
                  Review the payment reference and supporting records.
                  Payment verification does not establish bank availability.
                </p>
                <label className="customer-payment-confirm">
                  <input required type="checkbox"/>
                  I reviewed the supporting payment evidence.
                </label>
                <div className="customer-payment-actions">
                  <button disabled={busy}>Confirm Payment Verification</button>
                  <button className="quiet" type="button" disabled={busy}
                    onClick={() => setAction('')}>Cancel</button>
                </div>
                {feedbackFor(`verify-${payment.id}`)}
              </form>}
          </>}

          {payment.status === 'VERIFIED' &&
            !payment.bank_confirmed &&
            !payments.some(other =>
              other.id !== payment.id &&
              other.payment_reference === payment.payment_reference
            ) && <>
              <button type="button" className="quiet" disabled={busy}
                onClick={() => {
                  setAction(action === `bank-${payment.id}`
                    ? '' : `bank-${payment.id}`);
                  setFeedback(null);
                }}>
                Review Bank Availability
              </button>
              {action === `bank-${payment.id}` &&
                <form onSubmit={event => {
                  event.preventDefault();
                  const fields = new FormData(event.currentTarget);
                  void execute(
                    () => api(
                      `customer-payments/${payment.id}/bank-confirm/`,
                      'POST',
                      {
                        bank_reference: fields.get('bank_reference'),
                        confirmation_date: fields.get('confirmation_date'),
                        confirmation_method: fields.get('confirmation_method'),
                        confirmation_note: fields.get('confirmation_note'),
                      },
                    ),
                    'Bank availability confirmed and audited. Recheck Installation Scheduling.'
                  );
                }}>
                  <p>
                    Irreversible audited confirmation. Verify that funds
                    are actually available against your bank evidence.
                  </p>
                  <div className="grid">
                    <label>Bank reference
                      <input required name="bank_reference"
                        maxLength={150} disabled={busy}/>
                    </label>
                    <label>Funds-available date
                      <input required type="date" name="confirmation_date"
                        disabled={busy}/>
                    </label>
                    <label>Confirmation method
                      <input required name="confirmation_method"
                        maxLength={100} disabled={busy}/>
                    </label>
                    <label>Bank confirmation explanation
                      <textarea required name="confirmation_note"
                        maxLength={2000} disabled={busy}/>
                    </label>
                  </div>
                  <label className="customer-payment-confirm">
                    <input required type="checkbox"/>
                    I reviewed the referenced evidence of bank availability.
                  </label>
                  <div className="customer-payment-actions">
                    <button disabled={busy}>Confirm Bank Availability</button>
                    <button className="quiet" type="button" disabled={busy}
                      onClick={() => setAction('')}>Cancel</button>
                  </div>
                  {feedbackFor(`bank-${payment.id}`)}
                </form>}
            </>}
        </div>
      )}

      {feedback && !action && <p
        className={`customer-payment-feedback ${feedback.kind}`}
        role={feedback.kind === 'error' ? 'alert' : 'status'}>
        {feedback.text}
      </p>}
    </>}
  </section>;
}
