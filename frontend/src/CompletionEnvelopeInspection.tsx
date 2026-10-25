import { useState } from 'react';

type API = <T>(path: string, method?: string, data?: unknown) => Promise<T>;

type Attempt = {
  attempt_id: string;
  project_id: string;
  release_package_id: string;
  release_package_digest: string;
  provider_account_id: string;
  provider_envelope_id: string | null;
  state: string;
  created_at: string;
  first_send_started_at: string | null;
  provider_authenticated: boolean;
  signature_completion_verified: boolean;
  send_available: boolean;
};

export function CompletionEnvelopeInspection({ api }: { api: API }) {
  const [id, setId] = useState('');
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function inspect() {
    setAttempt(null);
    setError('');
    const requestedId = id.trim().toLowerCase();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(requestedId)) {
      setError('Enter a valid completion-envelope attempt UUID.');
      return;
    }
    setBusy(true);
    try {
      setAttempt(await api<Attempt>(`completion-envelope-attempts/${requestedId}/`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return <section>
    <h2>Completion Envelope Inspection</h2>
    <p className="muted">Comptroller-only inspection of local records. This screen does not contact DocuSign or send documents.</p>
    <form onSubmit={e => { e.preventDefault(); void inspect(); }}>
      <label>Envelope attempt UUID
        <input value={id} onChange={e => { setId(e.target.value); setAttempt(null); setError(''); }} required />
      </label>
      <button disabled={busy}>{busy ? 'Inspecting...' : 'Inspect recorded attempt'}</button>
    </form>
    {error && <p role="alert" className="error">{error}</p>}
    {attempt && <div>
      <h3>Recorded attempt</h3>
      <p>State: <strong>{attempt.state}</strong></p>
      <p>Attempt: {attempt.attempt_id}</p>
      <p>Project: {attempt.project_id}</p>
      <p>Release package: {attempt.release_package_id}</p>
      <p>Provider account: {attempt.provider_account_id}</p>
      <p>Provider envelope: {attempt.provider_envelope_id || 'Not recorded'}</p>
      <p>Created: {new Date(attempt.created_at).toLocaleString()}</p>
      <p>Sending activity: {attempt.first_send_started_at ? new Date(attempt.first_send_started_at).toLocaleString() : 'Not recorded'}</p>
      <p><strong>Provider authentication: Not established</strong></p>
      <p><strong>Signature completion: Not verified</strong></p>
      <p><strong>Document sending: Unavailable</strong></p>
      <p className="muted">Local attempt records are not proof of signed completion certificates.</p>
    </div>}
  </section>;
}
