/*
 * Test-only integration of fictional Weekly Payroll register.
 * Role-based tab display is illustrative, NOT backend authorization.
 * No operational API, financial actions, or network access.
 */
import {
  PayrollWeeklyRegister4344,
  type WeeklyRegister4344,
} from './payroll-weekly-register-4344';
/*
 * TEST-ONLY copy of the approved payroll workspace.
 * Synthetic mapped data may be displayed within My Payroll.
 * NOT a permission boundary, registered route, or operational API.
 */
import {
  PayrollPersonalRecords4341,
  type PersonalReport4334,
} from './payroll-personal-records-4341';
/**
 * VERIDIAN approved Payroll & Compensation workspace preview.
 * FICTIONAL DATA ONLY. This component is NOT registered in main.tsx.
 *
 * Screen-level display restrictions are illustrative only.
 * Real authorization MUST be independently enforced by the backend.
 * No financial actions, endpoints, exports, or live data are enabled.
 */
import React, { useState } from 'react';

export type PayrollRole4325 =
  | 'CEO'
  | 'COMPTROLLER'
  | 'SALES_MANAGER'
  | 'INSTALLATION_MANAGER'
  | 'SALES_ASSOCIATE'
  | 'TECHNICIAN'
  | 'MARKETING'
  | 'ACCOUNTS_PAYABLE_ASSOCIATE'
  | 'DATABASE_ADMINISTRATOR';

type Tab4325 =
  | 'My Payroll'
  | 'Weekly Payroll'
  | 'Approvals'
  | 'Payment History'
  | 'Contractor Records'
  | 'Reports';

const TABS: readonly Tab4325[] = [
  'My Payroll',
  'Weekly Payroll',
  'Approvals',
  'Payment History',
  'Contractor Records',
  'Reports',
];

const MANAGEMENT: readonly PayrollRole4325[] = [
  'CEO', 'COMPTROLLER',
];

const TEAM_MANAGERS: readonly PayrollRole4325[] = [
  'SALES_MANAGER', 'INSTALLATION_MANAGER',
];

function availableTabs(role: PayrollRole4325): readonly Tab4325[] {
  if (MANAGEMENT.includes(role)) return TABS;
  if (TEAM_MANAGERS.includes(role)) {
    return TABS.filter(
      tab => tab !== 'Contractor Records'
    );
  }
  return [
    'My Payroll',
    'Payment History',
    'Reports',
  ];
}

function scopeLabel(role: PayrollRole4325): string {
  if (MANAGEMENT.includes(role)) {
    return 'Company-wide authorized payroll';
  }
  if (role === 'SALES_MANAGER') {
    return 'Own and authorized sales-associate payroll';
  }
  if (role === 'INSTALLATION_MANAGER') {
    return 'Own and authorized technician payroll';
  }
  return 'Personal payroll only';
}

const panel: React.CSSProperties = {
  backgroundColor: '#F7F8F5',
  border: '1px solid #D7E3E7',
  borderRadius: 12,
  padding: 20,
};

const shell: React.CSSProperties = {
  color: '#142B3B',
  fontFamily: 'Inter, Arial, sans-serif',
  maxWidth: 1080,
  margin: '0 auto',
  padding: 24,
};

const rows = [
  {
    person: 'Fictional Contractor A',
    earned: '$1,250.00',
    status: 'Pending manager review',
  },
  {
    person: 'Fictional Contractor B',
    earned: '$875.00',
    status: 'Awaiting Comptroller approval',
  },
];

function FictionalTable(): React.JSX.Element {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Contractor', 'Illustrative amount', 'Example status'].map(
              label => (
                <th
                  key={label}
                  scope="col"
                  style={{
                    textAlign: 'left',
                    padding: 12,
                    borderBottom: '1px solid #D7E3E7',
                  }}
                >
                  {label}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.person}>
              <td style={{ padding: 12 }}>{row.person}</td>
              <td style={{ padding: 12 }}>{row.earned}</td>
              <td style={{ padding: 12 }}>{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PayrollWorkspaceWeekly4345({
  role,
  report,
  weeklyReport,
}: {
  role: PayrollRole4325;
  report?: PersonalReport4334;
  weeklyReport?: WeeklyRegister4344;
}): React.JSX.Element {
  const [requestedTab, setRequestedTab] = useState<Tab4325>('My Payroll');
  const tabs = availableTabs(role);
  const activeTab = tabs.includes(requestedTab)
    ? requestedTab
    : 'My Payroll';

  const managerOrExecutive =
    MANAGEMENT.includes(role) || TEAM_MANAGERS.includes(role);

  return (
    <main
      style={shell}
      aria-label="VERIDIAN fictional Payroll and Compensation preview"
      data-preview-only="true"
    >
      <p style={{ color: '#087F75', fontWeight: 700 }}>
        VERIDIAN / PAYROLL &amp; COMPENSATION
      </p>
      <h1>Payroll &amp; Compensation</h1>
      <p>
        Dedicated payroll workspace — approved layout preview.
        Figures and names below are fictional.
      </p>
      <div
        role="status"
        style={{
          ...panel,
          backgroundColor: '#FFF6E8',
          marginBottom: 20,
        }}
      >
        <strong>Development preview only.</strong> No live payroll
        data, payment approval, disbursement, or report export is enabled.
        Backend authorization is required before release.
      </div>

      <p>
        <strong>Visible scope:</strong> {scopeLabel(role)}
      </p>

      <nav aria-label="Payroll sections" style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        margin: '20px 0',
      }}>
        {tabs.map(tab => (
          <button
            key={tab}
            type="button"
            aria-pressed={activeTab === tab}
            onClick={() => setRequestedTab(tab)}
            style={{
              padding: '10px 14px',
              borderRadius: 8,
              border: '1px solid #D7E3E7',
              backgroundColor: activeTab === tab ? '#087F75' : 'white',
              color: activeTab === tab ? 'white' : '#142B3B',
              cursor: 'pointer',
            }}
          >
            {tab}
          </button>
        ))}
      </nav>

      <section style={panel} aria-label={activeTab}>
        <h2>{activeTab}</h2>

        {activeTab === 'My Payroll' && (
          report
            ? <PayrollPersonalRecords4341 report={report} />
            : <>
            <p>
              Your individual earnings, approvals, scheduled payment
              dates, and actual payment history will appear here.
            </p>
            <p>
              <strong>Example only:</strong> Weekly period Monday–Sunday;
              scheduled payment Wednesday following the period.
            </p>
          </>
        )}

        {activeTab === 'Weekly Payroll' && managerOrExecutive && (
          <>
            <p>
              Review the weekly register within your authorized scope.
              No payroll amounts are calculated by this preview.
            </p>
            {weeklyReport
              ? <PayrollWeeklyRegister4344 report={weeklyReport} />
              : <FictionalTable />}
          </>
        )}

        {activeTab === 'Approvals' && managerOrExecutive && (
          <>
            <p>
              Sales Manager: authorized sales compensation review.
              Installation Manager: authorized technical compensation
              review. Comptroller: independent final approval and
              payment recording. No self-approval.
            </p>
            <FictionalTable />
          </>
        )}

        {activeTab === 'Payment History' && (
          <p>
            Approved and paid records will distinguish the compensation
            date, scheduled pay date, actual paid date, payment
            method/reference, and audited adjustments.
          </p>
        )}

        {activeTab === 'Contractor Records' &&
          MANAGEMENT.includes(role) && (
            <p>
              Authorized contractor engagement records and onboarding
              evidence. Compensation arrangements remain managed in
              the separate Contractor Compensation section.
            </p>
          )}

        {activeTab === 'Reports' && (
          <p>
            PDF and Excel exports will be provided only after the
            backend verifies identity, authorized scope, approval
            history, and financial evidence. Exports are disabled
            in this preview.
          </p>
        )}
      </section>

      <p style={{ marginTop: 20, fontSize: 13, color: '#526674' }}>
        Every Record. Every Decision. Every Step.
      </p>
    </main>
  );
}