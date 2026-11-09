/**
 * VERIDIAN 1907P-4384: isolated fictional Approvals composition.
 * NOT a permission gate, live route, approval service or payment action.
 * Role selection changes fictional preview display only.
 */
import React from 'react';
import {
  PayrollApprovalsReview4349,
  type ApprovalRole4349,
} from './payroll-approvals-review-4349';
import {
  mapFictionalApprovals4383,
} from './payroll-approvals-boundary-4383';

export function PayrollApprovalsComposition4384({
  fictionalSource,
  role,
}: {
  fictionalSource: unknown;
  role: ApprovalRole4349;
}): React.JSX.Element {
  const report = mapFictionalApprovals4383(fictionalSource);

  return (
    <PayrollApprovalsReview4349
      report={report}
      role={role}
    />
  );
}
