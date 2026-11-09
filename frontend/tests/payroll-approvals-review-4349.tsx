/**
 * ISOLATED FICTIONAL APPROVALS REVIEW ONLY.
 * Not an authentication, authorization, approval or payment service.
 * No database operations, network calls or mutable approval controls.
 *
 * The backend must independently verify scope, historical roles,
 * delegated authority, two distinct approvers and durable audit evidence.
 */
import React from 'react';

export type ApprovalRole4349 =
  | 'CEO'
  | 'COMPTROLLER'
  | 'SALES_MANAGER'
  | 'INSTALLATION_MANAGER';

export type ApprovalRow4349 = Readonly<{
  reference: string;
  recipient: string;
  workstream: 'SALES' | 'INSTALLATION';
  amount: string;
  requesterId: string;
  firstApproverId: string | null;
  finalApproverId: string | null;
  stage:
    | 'WAITING_MANAGER'
    | 'WAITING_COMPTROLLER'
    | 'APPROVED';
  auditEvidence: 'PENDING' | 'RECORDED';
  actualPaidDate: null;
}>;

export type ApprovalReview4349 = Readonly<{
  view: 'fictional_approvals_review_only';
  managerAuthorityVerified: false;
  comptrollerAuthorityVerified: false;
  liveApprovalAuthorized: false;
  rows: readonly ApprovalRow4349[];
}>;

function validate(report: ApprovalReview4349): void {
  if (
    !report ||
    report.view !== 'fictional_approvals_review_only' ||
    report.managerAuthorityVerified !== false ||
    report.comptrollerAuthorityVerified !== false ||
    report.liveApprovalAuthorized !== false ||
    !Array.isArray(report.rows) ||
    report.rows.length > 100
  ) {
    throw new Error('Unsafe approval review contract.');
  }

  const references = new Set<string>();

  for (const row of report.rows) {
    if (!row || typeof row !== 'object' ||
        typeof row.reference !== 'string' ||
        !/^TEST-[A-Z0-9-]{1,30}$/.test(row.reference) ||
        references.has(row.reference) ||
        typeof row.recipient !== 'string' ||
        !/^Fictional [A-Za-z ]{1,60}$/.test(row.recipient) ||
        !['SALES', 'INSTALLATION'].includes(row.workstream) ||
        typeof row.amount !== 'string' ||
        !/^(?:0|[1-9]\d*)\.\d{2}$/.test(row.amount) ||
        !Number.isSafeInteger(Number(row.amount) * 100) ||
        typeof row.requesterId !== 'string' ||
        !/^TEST-[A-Z0-9-]{1,30}$/.test(row.requesterId) ||
        !['WAITING_MANAGER', 'WAITING_COMPTROLLER', 'APPROVED']
          .includes(row.stage) ||
        !['PENDING', 'RECORDED'].includes(row.auditEvidence) ||
        row.actualPaidDate !== null) {
      throw new Error('Invalid fictional approval record.');
    }

    references.add(row.reference);

    for (const id of [row.firstApproverId, row.finalApproverId]) {
      if (id !== null &&
          (typeof id !== 'string' ||
           !/^TEST-[A-Z0-9-]{1,30}$/.test(id) ||
           id === row.requesterId)) {
        throw new Error('Self-approval or invalid approver.');
      }
    }

    if (
      row.firstApproverId !== null &&
      row.firstApproverId === row.finalApproverId
    ) {
      throw new Error('First and final approver must differ.');
    }

    if (row.stage === 'WAITING_MANAGER' &&
        (row.firstApproverId !== null ||
         row.finalApproverId !== null ||
         row.auditEvidence !== 'PENDING')) {
      throw new Error('Manager-pending approval state conflicts.');
    }

    if (row.stage === 'WAITING_COMPTROLLER' &&
        (row.firstApproverId === null ||
         row.finalApproverId !== null ||
         row.auditEvidence !== 'PENDING')) {
      throw new Error('Comptroller-pending state conflicts.');
    }

    if (row.stage === 'APPROVED' &&
        (row.firstApproverId === null ||
         row.finalApproverId === null ||
         row.auditEvidence !== 'RECORDED')) {
      throw new Error('Final approval requires two approvers and audit.');
    }
  }
}

function status(stage: ApprovalRow4349['stage']): string {
  switch (stage) {
    case 'WAITING_MANAGER': return 'Awaiting manager review';
    case 'WAITING_COMPTROLLER': return 'Awaiting Comptroller approval';
    case 'APPROVED': return 'Two approvals recorded';
  }
}

function money(amount: string): string {
  return '$' + Number(amount).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function PayrollApprovalsReview4349({
  report,
  role,
}: {
  report: ApprovalReview4349;
  role: ApprovalRole4349;
}): React.JSX.Element {
  validate(report);

  if (![
    'CEO', 'COMPTROLLER', 'SALES_MANAGER', 'INSTALLATION_MANAGER',
  ].includes(role)) {
    throw new Error('This fictional review requires a management role.');
  }

  const rows = report.rows.filter(row =>
    role === 'CEO' || role === 'COMPTROLLER' ||
    (role === 'SALES_MANAGER' && row.workstream === 'SALES') ||
    (role === 'INSTALLATION_MANAGER' &&
      row.workstream === 'INSTALLATION')
  );

  const cell: React.CSSProperties = {
    textAlign: 'left',
    padding: 12,
    borderBottom: '1px solid #D7E3E7',
    whiteSpace: 'nowrap',
  };

  return (
    <div
      aria-label="Fictional payroll approval review"
      data-test-only="true"
      style={{ color: '#142B3B' }}
    >
      <p>
        Fictional approval review only. The role selection changes
        display examples, not actual access rights.
      </p>
      <p>
        Manager review comes first. A different authorized Comptroller
        provides final approval. Self-approval is prohibited.
      </p>
      {rows.length === 0 ? (
        <p>No fictional approvals for this view.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{
            width: '100%',
            minWidth: 1100,
            borderCollapse: 'collapse',
          }}>
            <thead>
              <tr>
                {[
                  'Recipient', 'Workstream', 'Amount',
                  'Manager approval', 'Comptroller approval',
                  'Current stage', 'Audit evidence',
                ].map(title => (
                  <th scope="col" key={title} style={cell}>
                    {title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.reference}>
                  <td style={cell}>{row.recipient}</td>
                  <td style={cell}>{row.workstream}</td>
                  <td style={cell}>{money(row.amount)}</td>
                  <td style={cell}>
                    {row.firstApproverId === null
                      ? 'Pending' : 'Recorded approved'}
                  </td>
                  <td style={cell}>
                    {row.finalApproverId === null
                      ? 'Pending' : 'Recorded approved'}
                  </td>
                  <td style={cell}>{status(row.stage)}</td>
                  <td style={cell}>
                    {row.auditEvidence === 'RECORDED'
                      ? 'Fictional record present'
                      : 'Pending'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p style={{ fontSize: 13, color: '#526674' }}>
        Approval is not payment. No actual paid dates, financial
        actions, approval buttons or exports are enabled.
        Durable backend audit verification is still required.
      </p>
    </div>
  );
}