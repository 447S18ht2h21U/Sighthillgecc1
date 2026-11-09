/**
 * VERIDIAN 1907P-4398
 * FICTIONAL Contractor Records presentation boundary only.
 *
 * No actual files, tax identifiers, license images, banking data,
 * contractor activation, payroll authority, database calls or APIs.
 *
 * Onboarding status here is illustrative, not verified evidence.
 * Django must separately enforce real permissions and onboarding.
 */
import type {
  ContractorReview4354,
  ContractorRow4354,
} from './payroll-contractor-records-4354';

type Source4398 = Record<string, unknown>;

function object4398(value: unknown): Source4398 {
  if (value === null ||
      typeof value !== 'object' ||
      Array.isArray(value)) {
    throw new Error('Fictional contractor object required.');
  }
  return value as Source4398;
}

function reference4398(value: unknown): string {
  if (typeof value !== 'string' ||
      !/^TEST-[A-Z0-9-]{1,36}$/.test(value)) {
    throw new Error('Synthetic engagement reference required.');
  }
  return value;
}

function date4398(value: unknown): string {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error('Invalid engagement date.');
  }

  const parsed = new Date(value + 'T00:00:00.000Z');

  if (!Number.isFinite(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10) !== value) {
    throw new Error('Noncanonical engagement date.');
  }

  return value;
}

type Evidence4398 = 'PENDING' | 'APPROVED' | 'REJECTED';

function evidence4398(value: unknown): Evidence4398 {
  if (
    value !== 'PENDING' &&
    value !== 'APPROVED' &&
    value !== 'REJECTED'
  ) {
    throw new Error('Invalid fictional document status.');
  }
  return value;
}

export function mapFictionalContractors4398(
  payload: unknown
): ContractorReview4354 {
  const source = object4398(payload);

  if (
    source.view !== 'fictional_contractor_records_only' ||
    source.backend_access_verified !== false ||
    source.onboarding_authority_granted !== false ||
    source.live_payroll_authorized !== false ||
    source.payment_actions_authorized !== false ||
    !Array.isArray(source.rows) ||
    source.rows.length > 100
  ) {
    throw new Error('Unsafe contractor source contract.');
  }

  const references = new Map<string, ContractorRow4354>();

  const rows: ContractorRow4354[] = source.rows.map(raw => {
    const item = object4398(raw);
    const reference = reference4398(item.reference);

    if (references.has(reference)) {
      throw new Error('Duplicate engagement reference.');
    }

    if (
      typeof item.contractor_id !== 'string' ||
      !/^TEST-CTR-[A-Z0-9-]{1,24}$/.test(item.contractor_id) ||
      typeof item.display_name !== 'string' ||
      !/^Fictional Contractor [A-Za-z ]{1,45}$/.test(item.display_name) ||
      (item.engagement_status !== 'PENDING' &&
       item.engagement_status !== 'ACTIVE' &&
       item.engagement_status !== 'ENDED') ||
      typeof item.payment_eligible !== 'boolean'
    ) {
      throw new Error('Invalid fictional engagement identity.');
    }

    const startDate = date4398(item.start_date);
    const endDate = item.end_date === null
      ? null
      : date4398(item.end_date);

    const w9 = evidence4398(item.w9);
    const driversLicense = evidence4398(item.drivers_license);
    const agreement = evidence4398(item.agreement);

    const returnOf = item.return_of === null
      ? null
      : reference4398(item.return_of);

    const complete =
      w9 === 'APPROVED' &&
      driversLicense === 'APPROVED' &&
      agreement === 'APPROVED';

    if (
      (endDate !== null && endDate < startDate) ||
      returnOf === reference ||
      (item.engagement_status === 'ACTIVE' &&
        (!complete || endDate !== null ||
         item.payment_eligible !== true)) ||
      (item.engagement_status !== 'ACTIVE' &&
        item.payment_eligible !== false) ||
      (item.engagement_status === 'ENDED' &&
        endDate === null) ||
      (item.engagement_status === 'PENDING' &&
        endDate !== null)
    ) {
      throw new Error('Unsafe onboarding or eligibility state.');
    }

    const row: ContractorRow4354 = {
      reference,
      contractorId: item.contractor_id,
      displayName: item.display_name,
      returnOf,
      engagementStatus: item.engagement_status,
      startDate,
      endDate,
      w9,
      driversLicense,
      agreement,
      paymentEligible: item.payment_eligible,
    } as ContractorRow4354;

    references.set(reference, row);
    return row;
  });

  for (const row of rows) {
    if (row.returnOf === null) continue;

    const previous = references.get(row.returnOf);

    if (
      !previous ||
      previous.contractorId !== row.contractorId ||
      previous.engagementStatus !== 'ENDED' ||
      previous.endDate === null ||
      previous.endDate >= row.startDate
    ) {
      throw new Error('Invalid historical return engagement.');
    }
  }

  // Explicit allowlist strips source-only fields. This preview
  // cannot attach documents or activate a real contractor.
  return {
    view: 'fictional_contractor_records_only',
    backendAccessVerified: false,
    onboardingAuthorityGranted: false,
    livePayrollAuthorized: false,
    rows,
  };
}

export function contractorBoundaryGrantsLiveAccess4398(): false {
  return false;
}
