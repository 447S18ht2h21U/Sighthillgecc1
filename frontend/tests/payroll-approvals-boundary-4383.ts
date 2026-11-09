/**
 * VERIDIAN 1907P-4383: Fictional approvals boundary only.
 * No identity verification, actual authorization, database access,
 * approval execution, payments, exports, or API registration.
 * Never feed real personal or financial records to this prototype.
 */

type Source4383 = Record<string, unknown>;

function obj4383(value: unknown): Source4383 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Fictional approvals object required.');
  }
  return value as Source4383;
}

function id4383(value: unknown): string {
  if (typeof value !== 'string' ||
      !/^TEST-[A-Z0-9-]{1,30}$/.test(value)) {
    throw new Error('Only synthetic TEST identifiers permitted.');
  }
  return value;
}

function optionalId4383(value: unknown): string | null {
  return value === null ? null : id4383(value);
}

export function mapFictionalApprovals4383(payload: unknown) {
  const source = obj4383(payload);

  if (
    source.view !== 'fictional_approvals_review_only' ||
    source.manager_authority_verified !== false ||
    source.comptroller_authority_verified !== false ||
    source.live_approval_authorized !== false ||
    source.payment_actions_authorized !== false ||
    source.actual_paid_date_verified !== false ||
    !Array.isArray(source.rows) ||
    source.rows.length > 100
  ) {
    throw new Error('Unsafe approvals source boundary.');
  }

  const references = new Set<string>();

  const rows = source.rows.map(raw => {
    const row = obj4383(raw);
    const reference = id4383(row.reference);
    const requesterId = id4383(row.requester_id);
    const firstApproverId = optionalId4383(row.first_approver_id);
    const finalApproverId = optionalId4383(row.final_approver_id);

    if (references.has(reference)) {
      throw new Error('Duplicate fictional approval reference.');
    }
    references.add(reference);

    const recipient = row.recipient;
    const workstream = row.workstream;
    const amount = row.amount;
    const stage = row.stage;
    const auditEvidence = row.audit_evidence;

    if (
      typeof recipient !== 'string' ||
      !/^Fictional [A-Za-z ]{1,60}$/.test(recipient) ||
      (workstream !== 'SALES' && workstream !== 'INSTALLATION') ||
      typeof amount !== 'string' ||
      !/^(?:0|[1-9]\d{0,11})\.\d{2}$/.test(amount) ||
      !Number.isSafeInteger(Number(amount) * 100) ||
      !['WAITING_MANAGER', 'WAITING_COMPTROLLER', 'APPROVED']
        .includes(stage as string) ||
      !['PENDING', 'RECORDED'].includes(auditEvidence as string) ||
      row.actual_paid_date !== null ||
      row.actual_paid_date_verified !== false ||
      firstApproverId === requesterId ||
      finalApproverId === requesterId ||
      (firstApproverId !== null &&
       firstApproverId === finalApproverId)
    ) {
      throw new Error('Unsafe fictional approval row.');
    }

    if (
      (stage === 'WAITING_MANAGER' &&
       (firstApproverId !== null ||
        finalApproverId !== null ||
        auditEvidence !== 'PENDING')) ||
      (stage === 'WAITING_COMPTROLLER' &&
       (firstApproverId === null ||
        finalApproverId !== null ||
        auditEvidence !== 'PENDING')) ||
      (stage === 'APPROVED' &&
       (firstApproverId === null ||
        finalApproverId === null ||
        auditEvidence !== 'RECORDED'))
    ) {
      throw new Error('Conflicting fictional approval stage.');
    }

    // Explicit allowlist: no source identifiers, banking details,
    // tax data, payment controls, or unexpected fields reach React.
    return {
      reference,
      recipient,
      workstream: workstream as 'SALES' | 'INSTALLATION',
      amount,
      requesterId,
      firstApproverId,
      finalApproverId,
      stage: stage as
        'WAITING_MANAGER' | 'WAITING_COMPTROLLER' | 'APPROVED',
      auditEvidence: auditEvidence as 'PENDING' | 'RECORDED',
      actualPaidDate: null as null,
    };
  });

  return {
    view: 'fictional_approvals_review_only' as const,
    managerAuthorityVerified: false as const,
    comptrollerAuthorityVerified: false as const,
    liveApprovalAuthorized: false as const,
    rows,
  };
}

export function approvalsBoundaryGrantsLiveAccess4383(): false {
  return false;
}
