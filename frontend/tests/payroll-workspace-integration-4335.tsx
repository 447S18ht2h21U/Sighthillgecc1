/**
 * Test-only composition of the approved VERIDIAN payroll workspace
 * and previously verified personal-payroll record renderer.
 *
 * The supplied report is synthetic, already mapped test data.
 * This is NOT an authentication, authorization, or network boundary.
 * No live page registration, exports, approvals, or disbursements.
 */
import React from 'react';
import {
  PayrollWorkspacePreview4325,
  type PayrollRole4325,
} from '../src/PayrollWorkspacePreview4325';
import {
  PayrollPersonalRecords4334,
  type PersonalReport4334,
} from './payroll-personal-records-4334';

export function PayrollWorkspaceIntegration4335({
  role,
  report,
}: {
  role: PayrollRole4325;
  report: PersonalReport4334;
}): React.JSX.Element {
  if (
    report.view !== 'my_payroll_test_only' ||
    report.livePayrollAuthorized !== false ||
    report.paymentActionsAvailable !== false ||
    report.exportsAvailable !== false
  ) {
    throw new Error('Unsafe payroll integration contract.');
  }

  return (
    <main data-payroll-integration="isolated-test-only">
      <PayrollWorkspacePreview4325 role={role} />
      <section aria-label="Isolated personal payroll contract review">
        <p>
          Synthetic contract verification only. This section is not
          part of operational navigation.
        </p>
        <PayrollPersonalRecords4334 report={report} />
      </section>
    </main>
  );
}