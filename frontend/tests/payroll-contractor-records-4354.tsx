/**
 * FICTIONAL CONTRACTOR RECORDS REVIEW - TEST ONLY.
 *
 * Document statuses are illustrative metadata, NEVER actual files.
 * Do not pass W-9 contents, license images, tax IDs or bank data here.
 * UI role selection provides no real authorization.
 * No live activation, access, enrollment, edits or payments.
 */
import React from 'react';

type Evidence4354 = 'PENDING' | 'APPROVED' | 'REJECTED';

export type ContractorRow4354 = Readonly<{
  reference: string;
  contractorId: string;
  displayName: string;
  returnOf: string | null;
  engagementStatus: 'PENDING' | 'ACTIVE' | 'ENDED';
  startDate: string;
  endDate: string | null;
  w9: Evidence4354;
  driversLicense: Evidence4354;
  agreement: Evidence4354;
  paymentEligible: boolean;
}>;

export type ContractorReview4354 = Readonly<{
  view: 'fictional_contractor_records_only';
  backendAccessVerified: false;
  onboardingAuthorityGranted: false;
  livePayrollAuthorized: false;
  rows: readonly ContractorRow4354[];
}>;

type Viewer4354 = 'CEO' | 'COMPTROLLER';

function validDate(value: unknown): value is string {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(date.getTime()) &&
    date.toISOString().slice(0, 10) === value;
}

function validate(report: ContractorReview4354): void {
  if (!report || report.view !== 'fictional_contractor_records_only' ||
      report.backendAccessVerified !== false ||
      report.onboardingAuthorityGranted !== false ||
      report.livePayrollAuthorized !== false ||
      !Array.isArray(report.rows) || report.rows.length > 100) {
    throw new Error('Unsafe contractor review contract.');
  }

  const references = new Map<string, ContractorRow4354>();

  for (const row of report.rows) {
    if (!row || typeof row !== 'object' ||
        typeof row.reference !== 'string' ||
        !/^TEST-[A-Z0-9-]{1,36}$/.test(row.reference) ||
        references.has(row.reference) ||
        typeof row.contractorId !== 'string' ||
        !/^TEST-CTR-[A-Z0-9-]{1,24}$/.test(row.contractorId) ||
        typeof row.displayName !== 'string' ||
        !/^Fictional Contractor [A-Za-z ]{1,45}$/.test(row.displayName) ||
        !['PENDING', 'ACTIVE', 'ENDED']
          .includes(row.engagementStatus) ||
        !validDate(row.startDate) ||
        (row.endDate !== null &&
          (!validDate(row.endDate) || row.endDate < row.startDate)) ||
        !['PENDING', 'APPROVED', 'REJECTED'].includes(row.w9) ||
        !['PENDING', 'APPROVED', 'REJECTED'].includes(row.driversLicense) ||
        !['PENDING', 'APPROVED', 'REJECTED'].includes(row.agreement) ||
        typeof row.paymentEligible !== 'boolean' ||
        (row.returnOf !== null &&
          (typeof row.returnOf !== 'string' ||
           !/^TEST-[A-Z0-9-]{1,36}$/.test(row.returnOf) ||
           row.returnOf === row.reference))) {
      throw new Error('Invalid fictional contractor engagement.');
    }

    const complete = row.w9 === 'APPROVED' &&
      row.driversLicense === 'APPROVED' &&
      row.agreement === 'APPROVED';

    if (
      (row.engagementStatus === 'ACTIVE' &&
        (!complete || row.endDate !== null || !row.paymentEligible)) ||
      (row.engagementStatus !== 'ACTIVE' && row.paymentEligible) ||
      (row.engagementStatus === 'ENDED' && row.endDate === null) ||
      (row.engagementStatus === 'PENDING' && row.endDate !== null)
    ) {
      throw new Error('Activation or payment eligibility conflict.');
    }

    references.set(row.reference, row);
  }

  for (const row of report.rows) {
    if (row.returnOf !== null) {
      const previous = references.get(row.returnOf);
      if (!previous || previous.contractorId !== row.contractorId ||
          previous.engagementStatus !== 'ENDED' ||
          previous.endDate === null ||
          previous.endDate >= row.startDate) {
        throw new Error('Invalid historical return engagement linkage.');
      }
    }
  }
}

function documentStatus(value: Evidence4354): string {
  switch (value) {
    case 'APPROVED': return 'Approved';
    case 'PENDING': return 'Pending review';
    case 'REJECTED': return 'Rejected';
  }
}

export function PayrollContractorRecords4354({
  report,
  viewer,
}: {
  report: ContractorReview4354;
  viewer: Viewer4354;
}): React.JSX.Element {
  validate(report);

  if (viewer !== 'CEO' && viewer !== 'COMPTROLLER') {
    throw new Error('Contractor records preview restricted.');
  }

  const cell: React.CSSProperties = {
    textAlign: 'left',
    padding: '10px 12px',
    borderBottom: '1px solid #D7E3E7',
    verticalAlign: 'top',
    whiteSpace: 'nowrap',
  };

  return (
    <div
      data-test-only="true"
      aria-label="Fictional contractor records review"
      style={{ color: '#142B3B' }}
    >
      <p>
        Fictional engagement and onboarding status only.
        No identity documents, tax information or bank details.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          minWidth: 1380,
          borderCollapse: 'collapse',
        }}>
          <thead>
            <tr>
              {[
                'Contractor', 'Engagement', 'Status',
                'Start date', 'End date', 'W-9',
                'Driver license', 'Signed agreement',
                'Payment eligibility', 'Engagement history',
              ].map(label => (
                <th key={label} scope="col" style={cell}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.rows.map(row => (
              <tr key={row.reference}>
                <td style={cell}>{row.displayName}</td>
                <td style={cell}>{row.reference}</td>
                <td style={cell}>{row.engagementStatus}</td>
                <td style={cell}>{row.startDate}</td>
                <td style={cell}>
                  {row.endDate ?? 'Not ended'}
                </td>
                <td style={cell}>{documentStatus(row.w9)}</td>
                <td style={cell}>
                  {documentStatus(row.driversLicense)}
                </td>
                <td style={cell}>
                  {documentStatus(row.agreement)}
                </td>
                <td style={cell}>
                  {row.paymentEligible
                    ? 'Eligible in fictional record'
                    : 'Not eligible'}
                </td>
                <td style={cell}>
                  {row.returnOf === null
                    ? 'Original engagement'
                    : `Return after ${row.returnOf}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 13, color: '#526674' }}>
        This is a display preview, not onboarding approval or
        payment authorization. Contractor compensation arrangements
        remain in the separate Contractor Compensation section.
        Live access and document verification require backend controls.
      </p>
    </div>
  );
}