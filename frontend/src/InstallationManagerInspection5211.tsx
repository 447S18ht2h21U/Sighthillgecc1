import { useEffect, useState } from 'react';
type API = <T>(
  path: string, method?: string, data?: unknown
) => Promise<T>;
type EquipmentInventory5215 = {
  project_id: string;
  msr_id: string | null;
  status: string;
  units: { unit_id: string }[];
  read_only: boolean;
  trusted_installation_evidence: boolean;
  installation_authorized: boolean;
  final_receipt_issuance_authorized: boolean;
  completion_authorized: boolean;
};

type Workspace = {
  project_id: string;
  state: string;
  internal_review_state: string;
  questions: { id: string; text: string }[];
  answers_recorded_by_this_endpoint: boolean;
  provider_signature_verified: boolean;
  receipt_issuance_authorized: boolean;
  project_completion_authorized: boolean;
};
const reviewStates: Record<string, string> = {
  NOT_READY: 'Inspection review requirements are incomplete.',
  NOT_RECORDED: 'No installation inspection has been recorded.',
  AWAITING_INDEPENDENT_REVIEW:
    'An internal inspection has been recorded and is awaiting Comptroller review.',
  INTERNAL_CANDIDATE_ACCEPTED:
    'The Comptroller accepted the internal inspection candidate. DocuSign verification is still required.',
  INTERNAL_CANDIDATE_REJECTED:
    'The Comptroller rejected the internal inspection candidate. Corrective action is required.',
  EVIDENCE_REQUIRES_ATTENTION:
    'The internal inspection evidence could not be verified. Further review is required.',
};

const states: Record<string, string> = {
  APPROVED_MSR_REQUIRED: 'A current approved Master Sales Record is required.',
  COMPLETED_INSTALLATION_REQUIRED: 'The installation must be recorded as completed before the inspection review can proceed.',
  INSPECTION_ALREADY_RECORDED: 'An inspection candidate is already recorded. Review its history rather than creating a duplicate.',
  READY_FOR_INSPECTION_REVIEW: 'The installation record is ready for inspection review. Verified DocuSign findings and signature are still required.',
};
export function InstallationManagerInspection5211({
  api, projectId,
}: {
  api: API;
  projectId: string;
}) {
  const [data, setData] = useState<Workspace | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [inventory, setInventory] = useState<EquipmentInventory5215 | null>(null);
  const [inventoryError, setInventoryError] = useState('');
  const [inventoryLoading, setInventoryLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError('');
    void api<Workspace>(
      `im-inspection-workspace/${encodeURIComponent(projectId)}/`
    ).then(result => {
      if (!cancelled) {
        if (
          result.project_id !== projectId ||
          !Object.prototype.hasOwnProperty.call(
            reviewStates, result.internal_review_state
          ) ||
          result.answers_recorded_by_this_endpoint !== false ||
          result.provider_signature_verified !== false ||
          result.receipt_issuance_authorized !== false ||
          result.project_completion_authorized !== false
        ) {
          setError('Inspection workspace failed safety verification.');
        } else {
          setData(result);
        }
      }
    }).catch((reason: unknown) => {
      if (!cancelled) {
        setError(reason instanceof Error
          ? reason.message
          : 'Unable to load inspection workspace.');
      }
    });
    return () => { cancelled = true; };
  }, [api, projectId, revision]);
  useEffect(() => {
    let cancelled = false;
    setInventory(null);
    setInventoryError('');
    setInventoryLoading(true);

    void api<EquipmentInventory5215>(
      `operational-projects/${encodeURIComponent(projectId)}/equipment-unit-inventory/`
    ).then(result => {
      if (cancelled) return;
      if (
        result.project_id !== projectId ||
        result.read_only !== true ||
        result.trusted_installation_evidence !== false ||
        result.installation_authorized !== false ||
        result.final_receipt_issuance_authorized !== false ||
        result.completion_authorized !== false ||
        !Array.isArray(result.units) ||
        (result.status !== 'INVENTORY_UNAVAILABLE' &&
         result.status !== 'APPROVED_UNIT_LIST_AVAILABLE') ||
        (result.status === 'APPROVED_UNIT_LIST_AVAILABLE' &&
         (!result.msr_id || result.units.length === 0)) ||
        (result.status === 'INVENTORY_UNAVAILABLE' &&
         result.units.length !== 0)
      ) {
        setInventoryError('Equipment inventory failed safety verification.');
      } else {
        setInventory(result);
      }
    }).catch((reason: unknown) => {
      if (!cancelled) {
        setInventoryError(
          reason instanceof Error ? reason.message :
          'Unable to check equipment inventory.'
        );
      }
    }).finally(() => {
      if (!cancelled) setInventoryLoading(false);
    });

    return () => { cancelled = true; };
  }, [api, projectId, revision]);

  return (
    <section id="installation-manager-inspection" className="veridian-guide-banner veridian-guide-banner--info">
      <h4>Installation Manager inspection</h4>
      <p>
        Review the five required inspection findings below.
        The Installation Manager must personally complete the findings
        and sign and date through DocuSign in the authorized signing phase.
      </p>
      {!data && !error && <p>Loading inspection readiness...</p>}
      {data && (
        <>
          <p role="status">
            <strong>Inspection readiness: </strong>
            {states[data.state] ?? 'Inspection review unavailable.'}
          </p>
          <p role="status">
            <strong>Independent inspection review: </strong>
            {reviewStates[data.internal_review_state]}
          </p>
          <div role="status">
            <strong>Equipment inventory readiness: </strong>
            {inventoryLoading
              ? 'Checking the approved equipment list...'
              : inventoryError
                ? 'Unable to verify equipment readiness.'
                : inventory?.status === 'APPROVED_UNIT_LIST_AVAILABLE'
                  ? `${inventory.units.length} approved physical unit(s) identified. Serial numbers and independent verification must still be completed.`
                  : 'Approved equipment inventory missing or invalid. Physical-unit inspection entry is blocked.'}
          </div>
          {inventoryError && <p role="alert">{inventoryError}</p>}
          {!inventoryLoading &&
            !inventoryError &&
            inventory?.status === 'INVENTORY_UNAVAILABLE' && (
              <p>
                Next step: Ask the Sales Manager to review the equipment
                details in the Master Sales Record. An approved MSR cannot
                be edited directly; any correction requires an authorized,
                versioned revision. Recheck this section afterward.
              </p>
            )}
          <p className="muted">
            An approved equipment list does not prove that the equipment
            was installed, that serial numbers were verified, or that
            DocuSign signing is authorized.
          </p>
          <ol>
            {data.questions.map(item => (
              <li key={item.id}>{item.text}</li>
            ))}
          </ol>
          <p className="muted">
            These are review questions, not recorded answers.
            No signature, final Receipt, or project completion is
            authorized by this screen.
          </p>
          {(data.answers_recorded_by_this_endpoint ||
            data.provider_signature_verified ||
            data.receipt_issuance_authorized ||
            data.project_completion_authorized) && (
            <p role="alert">
              Unexpected inspection authority detected. Do not proceed.
            </p>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
      <button
        type="button"
        className="quiet"
        onClick={() => setRevision(v => v + 1)}
      >
        Refresh inspection readiness
      </button>
    </section>
  );
}
