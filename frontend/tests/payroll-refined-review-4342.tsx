/**
 * ISOLATED LOCAL REVIEW ONLY - all payroll records are fictional.
 * Neither role selection nor this page establishes authorization.
 * No backend fetch, payroll API, approvals, exports, or payments.
 */
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';

import {
  PayrollWorkspaceTab4341,
  type PayrollRole4325,
} from './payroll-workspace-tab-4341';

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
      <PayrollWorkspaceTab4341
        role={role}
        report={fictionalData}
      />
    </>
  );
}

const root = document.getElementById(
  'payroll-integrated-review-root'
);
if (!root) throw new Error('Isolated payroll preview root missing.');

createRoot(root).render(<Review />);