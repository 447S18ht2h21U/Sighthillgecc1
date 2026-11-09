/**
 * ISOLATED VERIDIAN MY PAYROLL DATA BOUNDARY.
 *
 * Converts an ALREADY AUTHORIZED Python screen candidate into the
 * approved test-only React presentation format.
 *
 * Pure allowlist mapping only. This module neither obtains permissions,
 * requests data, registers an API route, nor authorizes payments.
 */

import type {
  PersonalReport4334,
} from './payroll-personal-records-4334';

type Object4373 = Record<string, unknown>;
type Row4373 = PersonalReport4334['employeeRecords'][number];

function object4373(value: unknown): Object4373 {
  if (
    value === null ||
    typeof value !== 'object' ||
    Array.isArray(value)
  ) {
    throw new Error('Authorized payroll object required.');
  }
  return value as Object4373;
}

function date4373(value: unknown): string {
  if (
    typeof value !== 'string' ||
    !/^\d{4}-\d{2}-\d{2}$/.test(value)
  ) {
    throw new Error('Canonical payroll date required.');
  }
  const parsed = new Date(`${value}T00:00:00.000Z`);
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.toISOString().slice(0, 10) !== value
  ) {
    throw new Error('Invalid payroll date.');
  }
  return value;
}

function text4373(value: unknown, label: string): string {
  if (
    typeof value !== 'string' ||
    value.trim().length === 0 ||
    value.length > 120
  ) {
    throw new Error(`Invalid ${label}.`);
  }
  return value;
}

function rows4373(
  value: unknown,
  type: 'employee' | 'contractor',
  start: string,
  end: string,
): Row4373[] {
  if (!Array.isArray(value) || value.length > 1000) {
    throw new Error('Invalid payroll record collection.');
  }

  return value.map(raw => {
    const row = object4373(raw);

    if (row.compensation_type !== type) {
      throw new Error('Wrong payroll record type.');
    }

    const status = row.status;
    if (status !== 'APPROVED' && status !== 'PAID') {
      throw new Error('Only approved and paid records are permitted.');
    }

    const statusLabel = status === 'PAID'
      ? 'Paid'
      : 'Approved - Not Yet Paid';

    if (row.status_label !== statusLabel) {
      throw new Error('Conflicting payroll status.');
    }

    const amount = row.amount;
    if (
      typeof amount !== 'string' ||
      !/^(?:0|[1-9]\d{0,11})\.\d{2}$/.test(amount)
    ) {
      throw new Error('Exact payroll amount is required.');
    }

    const periodStart = date4373(row.period_start);
    const periodEnd = date4373(row.period_end);

    if (
      periodStart > periodEnd ||
      periodEnd < start ||
      periodStart > end
    ) {
      throw new Error('Invalid payroll reporting period.');
    }

    if (
      row.scheduled_payment_date !== null ||
      row.actual_paid_date !== null ||
      row.actual_paid_date_verified !== false
    ) {
      throw new Error('Unverified payment dates are prohibited.');
    }

    // Explicit allowlist: internal IDs, personal identifiers, audit
    // metadata, and unexpected source keys never enter the UI object.
    return {
      compensationType: type,
      periodStart,
      periodEnd,
      compensationKind: text4373(row.kind, 'compensation kind'),
      amount,
      status,
      statusLabel,
      paymentEvidenceStatus: text4373(
        row.payment_evidence_status,
        'payment evidence classification',
      ),
      scheduledPaymentDate: null,
      actualPaidDate: null,
      actualPaidDateVerified: false,
    };
  });
}

export function mapAuthorizedPersonalPayroll4373(
  payload: unknown,
): PersonalReport4334 {
  const source = object4373(payload);

  if (
    source.view !== 'my_payroll_test_only' ||
    source.amount_basis !== 'full_obligation_not_prorated' ||
    source.manager_or_company_scope_authorized !== false ||
    source.payment_actions_authorized !== false ||
    source.actual_paid_date_verified !== false ||
    source.live_payroll_authorized !== false
  ) {
    throw new Error('Unsafe payroll authorization or scope contract.');
  }

  const periodStart = date4373(source.period_start);
  const periodEnd = date4373(source.period_end);

  if (periodStart > periodEnd) {
    throw new Error('Invalid payroll report period.');
  }

  const employeeRecords = rows4373(
    source.employee_records, 'employee', periodStart, periodEnd,
  );
  const contractorRecords = rows4373(
    source.contractor_records, 'contractor', periodStart, periodEnd,
  );

  return {
    view: 'my_payroll_test_only',
    periodStart,
    periodEnd,
    employeeRecords,
    contractorRecords,
    paymentActionsAvailable: false,
    exportsAvailable: false,
    livePayrollAuthorized: false,
  };
}

export function personalBoundaryGrantsLiveAccess4373(): false {
  return false;
}