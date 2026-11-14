import { useState } from 'react';

type API = <T>(path: string, method?: string, data?: unknown) => Promise<T>;

type Challenge = {
  authorization_url: string;
  operation: string;
  send_enabled: boolean;
  provider_signature_verified: boolean;
  project_completion_authorized: boolean;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function InstallationInspectionOAuth4984({ api }: { api: API }) {
  const [projectId, setProjectId] = useState('');
  const [bindingId, setBindingId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function connect(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    const project = projectId.trim().toLowerCase();
    const binding = bindingId.trim().toLowerCase();

    if (!UUID_PATTERN.test(project) || !UUID_PATTERN.test(binding)) {
      setError('Enter valid project and inspection-association UUIDs.');
      return;
    }
    if (!confirmed) {
      setError('Confirm the sandbox read-only authorization first.');
      return;
    }

    setBusy(true);
    try {
      const response = await api<Challenge>(
        `inspection-evidence/${project}/oauth-read/`,
        'POST',
        {
          binding_id: binding,
          sandbox_read_confirmed: true,
        }
      );

      if (
        response.operation !== 'SANDBOX_INSPECTION_READ' ||
        response.send_enabled !== false ||
        response.provider_signature_verified !== false ||
        response.project_completion_authorized !== false ||
        typeof response.authorization_url !== 'string'
      ) {
        throw new Error('The OAuth safety response was incomplete.');
      }

      const destination = new URL(response.authorization_url);
      if (
        destination.origin !== 'https://account-d.docusign.com' ||
        destination.pathname !== '/oauth/auth'
      ) {
        throw new Error('Unexpected sandbox authorization destination.');
      }

      // Navigation follows a deliberate, confirmed user action.
      // The server's separate feature gates remain authoritative.
      window.location.assign(destination.toString());
    } catch (failure) {
      setError((failure as Error).message);
      setBusy(false);
    }
  }

  return (
    <section className="documents">
      <h3>Installation Inspection — DocuSign Sandbox Read</h3>
      <p className="muted">
        Comptroller-only development workflow. An inspection must already
        have retained evidence and a matching recorded envelope association.
        This action starts a read-only OAuth challenge; it does not send
        documents or verify the manager's signature.
      </p>
      <form onSubmit={e => { void connect(e); }}>
        <label>
          Project UUID
          <input
            value={projectId}
            onChange={e => setProjectId(e.target.value)}
            disabled={busy}
            required
          />
        </label>
        <label>
          Inspection envelope-association UUID
          <input
            value={bindingId}
            onChange={e => setBindingId(e.target.value)}
            disabled={busy}
            required
          />
        </label>
        <label style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-start',
          gap: '0.65rem',
        }}>
          <input
            type="checkbox"
            style={{ width: 'auto', flex: '0 0 auto', margin: 0 }}
            checked={confirmed}
            disabled={busy}
            onChange={e => setConfirmed(e.target.checked)}
          />
          I confirm that this is an authorized, read-only DocuSign
          development sandbox inspection.
        </label>
        <button type="submit" disabled={busy || !confirmed}>
          {busy ? 'Preparing sandbox authorization...' : 'Connect for sandbox read'}
        </button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      <p className="muted">
        Unverified evidence remains unverified until the provider-origin,
        signer identity, signature date, and document bindings are independently
        established. Project completion remains prohibited.
      </p>
    </section>
  );
}
