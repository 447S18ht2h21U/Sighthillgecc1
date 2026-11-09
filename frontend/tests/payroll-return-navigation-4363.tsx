/**
 * ISOLATED PAYROLL RETURN NAVIGATION.
 *
 * The host application must supply onReturnToProjects.
 * This wrapper neither grants payroll permissions nor changes
 * authentication state, financial records, or browser location.
 *
 * NOT REGISTERED IN LIVE NAVIGATION.
 */
import React from 'react';
import {
  PayrollWorkspaceReports4358,
} from './payroll-workspace-reports-4358';

type WorkspaceProps4363 =
  React.ComponentProps<typeof PayrollWorkspaceReports4358>;

export type PayrollReturnProps4363 = WorkspaceProps4363 & {
  onReturnToProjects: () => void;
};

export function PayrollReturnNavigation4363({
  onReturnToProjects,
  ...workspaceProps
}: PayrollReturnProps4363): React.JSX.Element {
  if (typeof onReturnToProjects !== 'function') {
    throw new Error('A verified host navigation callback is required.');
  }

  return (
    <section
      aria-label="Isolated Payroll and Compensation navigation review"
      data-payroll-return-preview="true"
    >
      <div style={{
        display: 'flex',
        justifyContent: 'flex-end',
        marginBottom: 16,
      }}>
        <button
          type="button"
          className="quiet"
          aria-label="Return to Customers & Projects"
          onClick={onReturnToProjects}
          style={{
            padding: '10px 14px',
            border: '1px solid #D7E3E7',
            borderRadius: 8,
            color: '#142B3B',
            backgroundColor: '#F7F8F5',
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          Return to Customers &amp; Projects
        </button>
      </div>
      <PayrollWorkspaceReports4358 {...workspaceProps} />
    </section>
  );
}