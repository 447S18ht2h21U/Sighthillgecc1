/**
 * VERIDIAN 1907P-4393: isolated fictional Payment History boundary.
 * Pure presentation translation only.
 * No real records, authorization, database, payment, API or exports.
 * Django must independently verify ownership and effective scope.
 */
import type { PaymentHistory4351 } from './payroll-payment-history-4351';

type Input = Record<string, unknown>;
type HistoryRow = PaymentHistory4351['rows'][number];

function object4393(value: unknown): Input {
  if (value === null || typeof value !== 'object' ||
      Array.isArray(value)) {
    throw new Error('Fictional history object required.');
  }
  return value as Input;
}

function id4393(value: unknown): string {
  if (typeof value !== 'string' ||
      !/^TEST-[A-Z0-9-]{1,30}$/.test(value)) {
    throw new Error('Synthetic history identifier required.');
  }
  return value;
}

function date4393(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error('Invalid history date.');
  }
  const parsed = new Date(`${value}T00:00:00.000Z`);
  if (!Number.isFinite(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10) !== value) {
    throw new Error('Noncanonical history date.');
  }
  return value;
}

function amount4393(value: unknown, adjustment: boolean): string {
  if (typeof value !== 'string' ||
      !/^-?(?:0|[1-9]\d{0,11})\.\d{2}$/.test(value) ||
      (value.startsWith('-') && !adjustment)) {
    throw new Error('Invalid exact compensation amount.');
  }
  const cents = Number(value.replace('.', ''));
  if (!Number.isSafeInteger(cents)) {
    throw new Error('Unsafe monetary precision.');
  }
  return value;
}

export function mapFictionalPaymentHistory4393(
  payload: unknown
): PaymentHistory4351 {
  const source = object4393(payload);

  if (
    source.view !== 'fictional_payment_history_only' ||
    source.backend_scope_verified !== false ||
    source.external_payment_evidence_verified !== false ||
    source.live_payment_authorized !== false ||
    source.payment_actions_authorized !== false ||
    !Array.isArray(source.rows) ||
    source.rows.length > 100
  ) {
    throw new Error('Unsafe Payment History source.');
  }

  const references = new Set<string>();

  const rows: HistoryRow[] = source.rows.map(raw => {
    const row = object4393(raw);
    const reference = id4393(row.reference);

    if (references.has(reference)) {
      throw new Error('Duplicate historical reference.');
    }
    references.add(reference);

    if (
      typeof row.recipient !== 'string' ||
      !/^Fictional [A-Za-z ]{1,60}$/.test(row.recipient) ||
      (row.category !== 'employee' &&
       row.category !== 'contractor') ||
      (row.kind !== 'COMPENSATION' &&
       row.kind !== 'ADJUSTMENT') ||
      !['DRAFT', 'APPROVED', 'PAID']
        .includes(row.recorded_status as string) ||
      typeof row.exception !== 'boolean' ||
      row.actual_paid_date !== null ||
      row.actual_paid_date_verified !== false
    ) {
      throw new Error('Unsafe historical payroll record.');
    }

    const adjustment = row.kind === 'ADJUSTMENT';
    const adjustmentOf = adjustment
      ? id4393(row.adjustment_of)
      : null;

    if (
      (adjustment && adjustmentOf === reference) ||
      (!adjustment && row.adjustment_of !== null)
    ) {
      throw new Error('Invalid historical adjustment link.');
    }

    const periodStart = date4393(row.period_start);
    const periodEnd = date4393(row.period_end);
    const compensationDate = date4393(row.compensation_date);
    const proposedPaymentDate = date4393(row.proposed_payment_date);
    const issuedDate = date4393(row.issued_date);
    const settlementCandidateDate =
      date4393(row.settlement_candidate_date);

    if (
      periodStart === null ||
      periodEnd === null ||
      periodStart > periodEnd
    ) {
      throw new Error('Invalid historical reporting period.');
    }

    const method = row.method;
    const paymentReference = row.payment_reference;

    if (
      (method !== null && method !== 'ACH' && method !== 'CHECK') ||
      (paymentReference !== null &&
       (typeof paymentReference !== 'string' ||
        !/^TEST-[A-Z0-9-]{1,30}$/.test(paymentReference))) ||
      (issuedDate === null &&
       (method !== null ||
        paymentReference !== null ||
        settlementCandidateDate !== null)) ||
      (issuedDate !== null &&
       (method === null ||
        paymentReference === null ||
        row.recorded_status !== 'PAID')) ||
      (settlementCandidateDate !== null &&
       issuedDate !== null &&
       settlementCandidateDate < issuedDate)
    ) {
      throw new Error('Conflicting issuance or settlement evidence.');
    }

    return {
      reference,
      recipient: row.recipient as string,
      category: row.category as 'employee' | 'contractor',
      kind: row.kind as 'COMPENSATION' | 'ADJUSTMENT',
      adjustmentOf,
      compensationDate,
      periodStart,
      periodEnd,
      amount: amount4393(row.amount, adjustment),
      recordedStatus: row.recorded_status as
        'DRAFT' | 'APPROVED' | 'PAID',
      proposedPaymentDate,
      issuedDate,
      settlementCandidateDate,
      method: method as 'ACH' | 'CHECK' | null,
      paymentReference: paymentReference as string | null,
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: row.exception as boolean,
    };
  });

  return {
    view: 'fictional_payment_history_only',
    backendScopeVerified: false,
    externalPaymentEvidenceVerified: false,
    livePaymentAuthorized: false,
    rows,
  };
}

export function historyBoundaryGrantsLiveAccess4393(): false {
  return false;
}
