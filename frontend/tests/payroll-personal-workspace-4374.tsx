/**
 * Isolated personal-payroll composition; synthetic test data only.
 * Reuses the approved six-tab workspace and aligned return control.
 * The translator validates presentation shape; it does NOT establish
 * identity, permission, ownership, or management authority.
 * Django must independently enforce those checks before any future
 * live integration. No API registration, payments, or exports.
 */
import React from 'react';
import { PayrollWorkspaceAligned4366 } from './payroll-workspace-aligned-4366';
import { mapAuthorizedPersonalPayroll4373 } from './payroll-personal-boundary-4373';

type Props4374 = Omit<
  React.ComponentProps<typeof PayrollWorkspaceAligned4366>,
  'report'
> & {
  authorizedPersonalPayload: unknown;
};

export function PayrollPersonalWorkspace4374({
  authorizedPersonalPayload,
  ...workspace
}: Props4374): React.JSX.Element {
  const report = mapAuthorizedPersonalPayroll4373(authorizedPersonalPayload);
  return <PayrollWorkspaceAligned4366 {...workspace} report={report} />;
}