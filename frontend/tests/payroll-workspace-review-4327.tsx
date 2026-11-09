/**
 * ISOLATED DEVELOPMENT REVIEW ONLY.
 * All roles are simulated; this is NOT authentication or authorization.
 * There are no financial API requests or operational payment actions.
 * Do not deploy or register this page as an operational VERIDIAN route.
 */
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  PayrollWorkspacePreview4325,
  type PayrollRole4325,
} from '../src/PayrollWorkspacePreview4325';

const reviewRoles: readonly {
  value: PayrollRole4325;
  label: string;
}[] = [
  { value: 'CEO', label: 'CEO' },
  { value: 'COMPTROLLER', label: 'Comptroller' },
  { value: 'SALES_MANAGER', label: 'Sales Manager' },
  { value: 'INSTALLATION_MANAGER', label: 'Installation Manager' },
  { value: 'SALES_ASSOCIATE', label: 'Sales Associate' },
  { value: 'TECHNICIAN', label: 'Technician' },
  { value: 'MARKETING', label: 'Marketing' },
  {
    value: 'ACCOUNTS_PAYABLE_ASSOCIATE',
    label: 'Accounts Payable Associate',
  },
  {
    value: 'DATABASE_ADMINISTRATOR',
    label: 'Database Administrator',
  },
];

function PayrollReview4327(): React.JSX.Element {
  const [role, setRole] = useState<PayrollRole4325>('COMPTROLLER');

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#EDF2F0',
      fontFamily: 'Inter, Arial, sans-serif',
      color: '#142B3B',
    }}>
      <header style={{
        padding: '16px 24px',
        backgroundColor: '#142B3B',
        color: 'white',
      }}>
        <strong>VERIDIAN — ISOLATED PAYROLL DESIGN REVIEW</strong>
      </header>

      <div style={{
        maxWidth: 1080,
        margin: '0 auto',
        padding: '20px 24px 0',
      }}>
        <label htmlFor="review-role">
          <strong>Simulate screen for position: </strong>
        </label>
        <select
          id="review-role"
          value={role}
          onChange={event => {
            setRole(event.target.value as PayrollRole4325);
          }}
          style={{
            padding: 10,
            border: '1px solid #D7E3E7',
            borderRadius: 8,
            backgroundColor: 'white',
            color: '#142B3B',
            marginLeft: 8,
          }}
        >
          {reviewRoles.map(item => (
            <option value={item.value} key={item.value}>
              {item.label}
            </option>
          ))}
        </select>

        <p style={{ fontSize: 13 }}>
          This selector only changes the fictional screen layout.
          It does not sign in as another user or grant permissions.
        </p>
      </div>

      <PayrollWorkspacePreview4325 role={role} />
    </div>
  );
}

const root = document.getElementById('payroll-review-root');
if (root === null) {
  throw new Error('Isolated payroll preview root is missing.');
}
createRoot(root).render(<PayrollReview4327 />);