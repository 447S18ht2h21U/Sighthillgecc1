/**
 * ISOLATED LOCAL REVIEW ONLY - all payroll records are fictional.
 * Neither role selection nor this page establishes authorization.
 * No backend fetch, payroll API, approvals, exports, or payments.
 */
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';

import {
  PayrollWorkspaceContractors4355,
  type PayrollRole4325,
} from './payroll-workspace-contractors-4355';

import {
  mapAuthorizedPersonalPayroll4332,
} from './payroll-personal-screen-mapper-4332.mjs';

import syntheticBackendReport from './payroll-synthetic-report-4339.json';

const fictionalData = mapAuthorizedPersonalPayroll4332(
  syntheticBackendReport
);

const roles: readonly PayrollRole4325[] = [
  'COMPTROLLER',
  'CEO',
  'SALES_MANAGER',
  'INSTALLATION_MANAGER',
  'SALES_ASSOCIATE',
  'TECHNICIAN',
  'MARKETING',
  'ACCOUNTS_PAYABLE_ASSOCIATE',
  'DATABASE_ADMINISTRATOR',
];


/*
 * Local fictional register. These are not operational records.
 * Historical manager authorization and live payroll stay disabled.
 */
const fictionalWeekly = {
  view: 'fictional_weekly_register_only',
  historicalRoleBindingVerified: false,
  managerAccessAuthorized: false,
  livePayrollAuthorized: false,
  rows: [
    {
      reference: 'TEST-A',
      recipient: 'Fictional Contractor A',
      category: 'contractor',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '1250.00',
      managerApproval: 'PENDING',
      comptrollerApproval: 'PENDING',
      scheduledDate: null,
      recordedStatus: 'DRAFT',
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: false,
    },
    {
      reference: 'TEST-B',
      recipient: 'Fictional Contractor B',
      category: 'contractor',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '875.00',
      managerApproval: 'APPROVED',
      comptrollerApproval: 'PENDING',
      scheduledDate: '2026-11-11',
      recordedStatus: 'DRAFT',
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: true,
    },
  ],
} as const;

/*
 * Fictional approval examples only.
 * No actual authority, verified historical roles,
 * trusted audit evidence, or payment transactions.
 */
const fictionalApprovals = {
  view: 'fictional_approvals_review_only',
  managerAuthorityVerified: false,
  comptrollerAuthorityVerified: false,
  liveApprovalAuthorized: false,
  rows: [
    {
      reference: 'TEST-SALES-A',
      recipient: 'Fictional Sales Associate',
      workstream: 'SALES',
      amount: '1250.00',
      requesterId: 'TEST-REQ-A',
      firstApproverId: null,
      finalApproverId: null,
      stage: 'WAITING_MANAGER',
      auditEvidence: 'PENDING',
      actualPaidDate: null,
    },
    {
      reference: 'TEST-TECH-B',
      recipient: 'Fictional Technician',
      workstream: 'INSTALLATION',
      amount: '875.00',
      requesterId: 'TEST-REQ-B',
      firstApproverId: 'TEST-MANAGER-B',
      finalApproverId: null,
      stage: 'WAITING_COMPTROLLER',
      auditEvidence: 'PENDING',
      actualPaidDate: null,
    },
    {
      reference: 'TEST-SALES-C',
      recipient: 'Fictional Sales Contractor',
      workstream: 'SALES',
      amount: '500.00',
      requesterId: 'TEST-REQ-C',
      firstApproverId: 'TEST-MANAGER-C',
      finalApproverId: 'TEST-COMPTROLLER-C',
      stage: 'APPROVED',
      auditEvidence: 'RECORDED',
      actualPaidDate: null,
    },
  ],
} as const;

/*
 * Synthetic records for visual testing only.
 * A recorded PAID status, issue date, or settlement candidate is
 * not proof of actual payment. No financial actions are enabled.
 */
const fictionalHistory = {
  view: 'fictional_payment_history_only',
  backendScopeVerified: false,
  externalPaymentEvidenceVerified: false,
  livePaymentAuthorized: false,
  rows: [
    {
      reference: 'TEST-PAY-A',
      recipient: 'Fictional Employee A',
      category: 'employee',
      kind: 'COMPENSATION',
      adjustmentOf: null,
      compensationDate: '2026-11-06',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '600.00',
      recordedStatus: 'APPROVED',
      proposedPaymentDate: '2026-11-11',
      issuedDate: null,
      settlementCandidateDate: null,
      method: null,
      paymentReference: null,
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: false,
    },
    {
      reference: 'TEST-PAY-B',
      recipient: 'Fictional Contractor B',
      category: 'contractor',
      kind: 'COMPENSATION',
      adjustmentOf: null,
      compensationDate: '2026-11-05',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '1250.00',
      recordedStatus: 'PAID',
      proposedPaymentDate: '2026-11-11',
      issuedDate: '2026-11-11',
      settlementCandidateDate: '2026-11-12',
      method: 'ACH',
      paymentReference: 'TEST-REF-B',
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: true,
    },
    {
      reference: 'TEST-ADJ-C',
      recipient: 'Fictional Contractor B',
      category: 'contractor',
      kind: 'ADJUSTMENT',
      adjustmentOf: 'TEST-PAY-B',
      compensationDate: '2026-11-05',
      periodStart: '2026-11-02',
      periodEnd: '2026-11-08',
      amount: '-50.00',
      recordedStatus: 'DRAFT',
      proposedPaymentDate: null,
      issuedDate: null,
      settlementCandidateDate: null,
      method: null,
      paymentReference: null,
      actualPaidDate: null,
      actualPaidDateVerified: false,
      exception: true,
    },
  ],
} as const;

/*
 * Fictional contractor engagement statuses only.
 * No real identity documents, onboarding authority or payment access.
 */
const fictionalContractors = {
  view: 'fictional_contractor_records_only',
  backendAccessVerified: false,
  onboardingAuthorityGranted: false,
  livePayrollAuthorized: false,
  rows: [
    {
      reference: 'TEST-CTR-A-01',
      contractorId: 'TEST-CTR-A',
      displayName: 'Fictional Contractor A',
      returnOf: null,
      engagementStatus: 'ENDED',
      startDate: '2026-01-05',
      endDate: '2026-06-30',
      w9: 'APPROVED',
      driversLicense: 'APPROVED',
      agreement: 'APPROVED',
      paymentEligible: false,
    },
    {
      reference: 'TEST-CTR-A-R01',
      contractorId: 'TEST-CTR-A',
      displayName: 'Fictional Contractor A',
      returnOf: 'TEST-CTR-A-01',
      engagementStatus: 'ACTIVE',
      startDate: '2026-09-01',
      endDate: null,
      w9: 'APPROVED',
      driversLicense: 'APPROVED',
      agreement: 'APPROVED',
      paymentEligible: true,
    },
    {
      reference: 'TEST-CTR-B-01',
      contractorId: 'TEST-CTR-B',
      displayName: 'Fictional Contractor B',
      returnOf: null,
      engagementStatus: 'PENDING',
      startDate: '2026-11-02',
      endDate: null,
      w9: 'APPROVED',
      driversLicense: 'PENDING',
      agreement: 'PENDING',
      paymentEligible: false,
    },
  ],
} as const;
function Review(): React.JSX.Element {
  const [role, setRole] = useState<PayrollRole4325>('COMPTROLLER');

  return (
    <>
      <aside style={{
        fontFamily: 'Inter, Arial, sans-serif',
        padding: 16,
        background: '#EAF4F2',
        color: '#142B3B',
        borderBottom: '2px solid #087F75',
      }}>
        <strong>LOCAL TEST PREVIEW - FICTIONAL PAYROLL ONLY</strong>
        <p>
          This position selector simulates appearance only.
          It cannot grant permissions or retrieve actual payroll.
        </p>
        <label htmlFor="payroll-review-role">
          Fictional position: {' '}
        </label>
        <select
          id="payroll-review-role"
          value={role}
          onChange={event =>
            setRole(event.target.value as PayrollRole4325)
          }
        >
          {roles.map(item => (
            <option key={item} value={item}>
              {item.replaceAll('_', ' ')}
            </option>
          ))}
        </select>
      </aside>
      <PayrollWorkspaceContractors4355
        role={role}
        report={fictionalData}
        weeklyReport={fictionalWeekly}
        approvalReport={fictionalApprovals}
        historyReport={fictionalHistory}
        contractorReport={fictionalContractors}
      />
    </>
  );
}

const root = document.getElementById(
  'payroll-integrated-review-root'
);
if (!root) throw new Error('Isolated payroll preview root missing.');

createRoot(root).render(<Review />);