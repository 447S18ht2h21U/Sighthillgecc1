import React, { useEffect, useState } from 'react';

type Api = <T,>(path: string, method?: string, data?: unknown) => Promise<T>;

type Unit = {
  unit_id: string;
  row_number: number;
  unit_number: number;
  brand: string;
  residential_system_type: string;
  model_number: string;
  description: string;
  category_of_work: string;
};

type Inventory = {
  project_id: string;
  msr_id: string | null;
  status: string;
  units: Unit[];
  read_only: boolean;
  trusted_installation_evidence: boolean;
  installation_authorized: boolean;
  final_receipt_issuance_authorized: boolean;
  completion_authorized: boolean;
};

export function EquipmentUnitSelection4872({
  api,
  projectId,
}: {
  api: Api;
  projectId: string;
}) {
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [unitId, setUnitId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [serialNumber, setSerialNumber] = useState('');
  const [capturedAt, setCapturedAt] = useState('');
  const [startsAt, setStartsAt] = useState('');
  const [notes, setNotes] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [feedback, setFeedback] = useState('');


  useEffect(() => {
    let active = true;
    setLoading(true);
    setInventory(null);
    setUnitId('');
    setError('');
    setSerialNumber('');
    setCapturedAt('');
    setStartsAt('');
    setNotes('');
    setConfirmed(false);
    setSubmitted(false);
    setFeedback('');

    void api<Inventory>(
      `operational-projects/${encodeURIComponent(projectId)}/equipment-unit-inventory/`
    ).then(result => {
      if (!active) return;
      if (
        result.project_id !== projectId ||
        result.read_only !== true ||
        result.trusted_installation_evidence !== false ||
        result.installation_authorized !== false ||
        result.final_receipt_issuance_authorized !== false ||
        result.completion_authorized !== false
      ) {
        setError('Equipment inventory response failed safety verification.');
      } else {
        setInventory(result);
      }
    }).catch(err => {
      if (active) setError((err as Error).message);
    }).finally(() => {
      if (active) setLoading(false);
    });

    return () => { active = false; };
  }, [api, projectId]);

  const available = inventory?.status === 'APPROVED_UNIT_LIST_AVAILABLE'
    && Array.isArray(inventory.units)
    && inventory.units.length > 0;
  const selected = available
    ? inventory.units.find(unit => unit.unit_id === unitId)
    : undefined;

  async function submitInspection(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !available || !selected || !inventory?.msr_id ||
      !serialNumber.trim() || !capturedAt || !startsAt ||
      notes.trim().length < 15 || notes.trim().length > 2000 ||
      !confirmed || submitting || submitted
    ) return;

    const submittedProject = projectId;
    const submittedUnit = selected.unit_id;
    const submittedMsr = inventory.msr_id;

    setSubmitting(true);
    setFeedback('');
    try {
      const result = await api<{
        project_id: string;
        msr_id: string;
        unit_id: string;
        status: string;
        trusted_installation_evidence: boolean;
        final_receipt_issuance_authorized: boolean;
        completion_authorized: boolean;
      }>(
        `operational-projects/${encodeURIComponent(submittedProject)}/record-equipment-unit-inspection/`,
        'POST',
        {
          msr_id: submittedMsr,
          unit_id: submittedUnit,
          serial_number: serialNumber.trim(),
          captured_at: new Date(capturedAt).toISOString(),
          installation_starts_at: new Date(startsAt).toISOString(),
          confirmed_in_person: true,
          inspection_notes: notes.trim(),
        },
      );
      if (
        result.project_id !== submittedProject ||
        result.msr_id !== submittedMsr ||
        result.unit_id !== submittedUnit ||
        result.status !== 'PENDING_INDEPENDENT_REVIEW' ||
        result.trusted_installation_evidence !== false ||
        result.final_receipt_issuance_authorized !== false ||
        result.completion_authorized !== false
      ) {
        throw new Error('Inspection response failed verification.');
      }
      setSubmitted(true);
      setFeedback('PENDING INDEPENDENT REVIEW — internal inspection claim recorded.');
    } catch (err) {
      setFeedback((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="installation-completion-guidance"
      aria-label="Equipment inspection and serial numbers">
      <h3>Equipment Inspection & Serial Numbers</h3>
      <p>
        Read-only identification from the current approved Master Sales Record.
        Selecting a unit does not record a serial number or verify an inspection.
      </p>
      {loading && <p role="status">Loading approved equipment inventory...</p>}
      {error && <p role="alert" style={{ color: '#B42318', fontWeight: 700 }}>
        {error}
      </p>}
      {!loading && !error && !available && (
        <p role="alert" style={{ color: '#B42318', fontWeight: 800 }}>
          EQUIPMENT INVENTORY MISSING OR INVALID — PHYSICAL-UNIT ENTRY BLOCKED
        </p>
      )}
      {available && (
        <>
          <label htmlFor="approved-physical-unit">Select approved equipment unit
            <select
              id="approved-physical-unit"
              value={unitId}
              onChange={event => setUnitId(event.target.value)}
            >
              <option value="">Select a unit</option>
              {inventory!.units.map(unit => (
                <option key={unit.unit_id} value={unit.unit_id}>
                  {unit.unit_id} — {unit.brand} {unit.model_number}
                </option>
              ))}
            </select>
          </label>
          {selected && (
            <div role="status">
              <p><strong>Unit:</strong> {selected.unit_id}</p>
              <p><strong>Brand:</strong> {selected.brand}</p>
              <p><strong>Model:</strong> {selected.model_number}</p>
              <p><strong>System:</strong> {selected.residential_system_type}</p>
              <p><strong>Description:</strong> {selected.description}</p>
              <p><strong>Work category:</strong> {selected.category_of_work}</p>
              <p><strong>Serial number:</strong> Not recorded by this screen</p>
            </div>
          )}
        </>
      )}
          {selected && (
            <form onSubmit={event => void submitInspection(event)}>
              <h4>Record Pending Physical-Unit Inspection</h4>
              <p>
                Development-only internal evidence. Record only a physical
                inspection you actually performed. This does not establish
                authenticated installation completion.
              </p>
              <label>Equipment serial number
                <input
                  required maxLength={120}
                  value={serialNumber}
                  onChange={event => setSerialNumber(event.target.value)}
                  disabled={submitting || submitted}
                />
              </label>
              <label>Actual observation date and time
                <input
                  type="datetime-local" required
                  value={capturedAt}
                  onChange={event => setCapturedAt(event.target.value)}
                  disabled={submitting || submitted}
                />
              </label>
              <label>Installation start date and time
                <input
                  type="datetime-local" required
                  value={startsAt}
                  onChange={event => setStartsAt(event.target.value)}
                  disabled={submitting || submitted}
                />
              </label>
              <label>Physical inspection notes (15–2000 characters)
                <textarea
                  required minLength={15} maxLength={2000}
                  rows={4} value={notes}
                  onChange={event => setNotes(event.target.value)}
                  disabled={submitting || submitted}
                />
              </label>
              <label>
                <input type="checkbox" required checked={confirmed}
                  onChange={event => setConfirmed(event.target.checked)}
                  disabled={submitting || submitted}
                />
                I personally inspected this physical unit in person,
                and the recorded information is accurate.
              </label>
              <button type="submit" disabled={
                submitting || submitted || !confirmed ||
                !serialNumber.trim() || !capturedAt || !startsAt ||
                notes.trim().length < 15
              }>
                {submitting ? 'Recording...' : 'Record Pending Inspection'}
              </button>
              {feedback && (
                <p role="status" style={{
                  fontWeight: 800,
                  color: submitted ? '#9A6700' : '#B42318',
                }}>{feedback}</p>
              )}
            </form>
          )}
      <p><strong>Evidence status:</strong> Identification only — not independently
        authenticated installation evidence.</p>
    </section>
  );
}
