/*
 * TEST-ONLY frontend mapping of Step 4331's ALREADY AUTHORIZED report.
 * This function is NOT authentication, permission checking, or an API.
 * Do not accept data supplied directly by a browser user as authority.
 * Only the existing backend permission/ownership gate may obtain records.
 * No network, storage, payments, exports or live integration.
 */

const allowedStatuses = new Set(['APPROVED', 'PAID']);

function exactDate(value) {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new TypeError('Canonical ISO date required.');
  }
  const date = new Date(value + 'T00:00:00.000Z');
  if (!Number.isFinite(date.getTime()) ||
      date.toISOString().slice(0, 10) !== value) {
    throw new TypeError('Invalid payroll date.');
  }
  return value;
}

function cents(value) {
  if (typeof value !== 'string' ||
      !/^(?:0|[1-9]\d*)\.\d{2}$/.test(value)) {
    throw new TypeError('Exact two-decimal amount required.');
  }
  const [whole, fraction] = value.split('.');
  const integer = Number(whole);
  if (!Number.isSafeInteger(integer) ||
      integer > Math.floor(Number.MAX_SAFE_INTEGER / 100)) {
    throw new TypeError('Amount exceeds safe display range.');
  }
  const result = integer * 100 + Number(fraction);
  if (!Number.isSafeInteger(result)) {
    throw new TypeError('Amount exceeds safe display range.');
  }
  return result;
}

function money(amountCents) {
  if (!Number.isSafeInteger(amountCents) || amountCents < 0) {
    throw new TypeError('Invalid integer cents.');
  }
  return '$' + (amountCents / 100).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function mapRows(rows, type, reportStart, reportEnd) {
  if (!Array.isArray(rows) || rows.length > 1000) {
    throw new TypeError('Invalid payroll record list.');
  }

  return rows.map(row => {
    if (row === null || typeof row !== 'object' ||
        Array.isArray(row) ||
        row.compensation_type !== type ||
        !allowedStatuses.has(row.status)) {
      throw new TypeError('Invalid compensation record.');
    }

    const expectedLabel = row.status === 'PAID'
      ? 'Paid'
      : 'Approved - Not Yet Paid';

    if (row.status_label !== expectedLabel) {
      throw new TypeError('Conflicting payroll status label.');
    }

    const start = exactDate(row.period_start);
    const end = exactDate(row.period_end);

    if (start > end || end < reportStart || start > reportEnd) {
      throw new TypeError('Invalid or nonoverlapping payroll period.');
    }

    if (typeof row.kind !== 'string' ||
        !row.kind || row.kind.length > 120 ||
        typeof row.payment_evidence_status !== 'string' ||
        !row.payment_evidence_status ||
        row.payment_evidence_status.length > 120) {
      throw new TypeError('Missing compensation classification.');
    }

    if (row.actual_paid_date !== null ||
        row.scheduled_payment_date !== null ||
        row.actual_paid_date_verified !== false) {
      throw new TypeError('Unverified payment date or evidence claim.');
    }

    const amountCents = cents(row.amount);

    // Strict output allowlist: never copy account, tax, banking,
    // identity or other unexpected backend fields to the UI.
    return Object.freeze({
      compensationType: type,
      periodStart: start,
      periodEnd: end,
      compensationKind: row.kind,
      amountCents,
      amount: money(amountCents),
      status: row.status,
      statusLabel: expectedLabel,
      paymentEvidenceStatus: row.payment_evidence_status,
      scheduledPaymentDate: null,
      actualPaidDate: null,
      actualPaidDateVerified: false,
    });
  });
}

export function mapAuthorizedPersonalPayroll4332(report) {
  if (report === null || typeof report !== 'object' ||
      Array.isArray(report) ||
      report.view !== 'my_payroll_test_only' ||
      report.amount_basis !== 'full_obligation_not_prorated' ||
      report.manager_or_company_scope_authorized !== false ||
      report.payment_actions_authorized !== false ||
      report.actual_paid_date_verified !== false ||
      report.live_payroll_authorized !== false) {
    throw new TypeError('Unexpected protected payroll contract.');
  }

  const start = exactDate(report.period_start);
  const end = exactDate(report.period_end);

  if (start > end) {
    throw new TypeError('Invalid report date range.');
  }

  const employee = mapRows(
    report.employee_records, 'employee', start, end
  );
  const contractor = mapRows(
    report.contractor_records, 'contractor', start, end
  );

  return Object.freeze({
    view: 'my_payroll_test_only',
    periodStart: start,
    periodEnd: end,
    employeeRecords: Object.freeze(employee),
    contractorRecords: Object.freeze(contractor),
    paymentActionsAvailable: false,
    exportsAvailable: false,
    livePayrollAuthorized: false,
  });
}