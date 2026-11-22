import React, { useEffect, useState } from 'react';

type Row = {
  id: string;
  type: string;
  person: string;
  kind: string;
  period_start: string;
  period_end: string;
  gross: string;
  deductions: string;
  net: string;
  status: string;
  approval_recorded_at: string | null;
  payment_recorded_at: string | null;
};

type PayrollResponse = {
  scope: string;
  read_only: boolean;
  rows: Row[];
};

export function OperationalWeeklyPayroll5465(): React.JSX.Element {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const response = await fetch('/api/payroll/weekly/', {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error('Payroll unavailable (HTTP ' + response.status + ').');
        }

        const result = await response.json() as PayrollResponse;
        if (result.scope !== 'COMPTROLLER_COMPANY_WIDE' ||
            result.read_only !== true ||
            !Array.isArray(result.rows)) {
          throw new Error('Unexpected payroll authorization response.');
        }

        if (!controller.signal.aborted) setRows(result.rows);
      } catch (reason) {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error
            ? reason.message : 'Unable to load payroll.');
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void load();
    return () => controller.abort();
  }, []);

  return (
    <section aria-label="Operational weekly payroll register">
      <p><strong>Company-wide payroll — Comptroller</strong></p>
      <p>
        Read-only obligations. Recorded payment dates do not independently
        verify bank settlement. No payment or approval actions are enabled.
      </p>

      {loading && <p role="status">Loading recorded payroll...</p>}
      {error && <p role="alert">{error}</p>}

      {!loading && !error && rows.length === 0 && (
        <p role="status">
          No employee or contractor payroll records exist in the
          current development database.
        </p>
      )}

      {!loading && !error && rows.length > 0 && (
        <>
          <p>{rows.length} record(s), up to the latest 100.</p>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              borderCollapse: 'collapse',
              width: '100%',
              minWidth: 1050,
              textAlign: 'left',
            }}>
              <thead>
                <tr>
                  {[
                    'Person', 'Type', 'Compensation', 'Period',
                    'Gross', 'Deductions', 'Net', 'Status',
                    'Approval recorded', 'Payment recorded',
                  ].map(label => (
                    <th key={label} scope="col" style={{
                      padding: 8,
                      borderBottom: '1px solid #D7E3E7',
                    }}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.type + row.id}>
                    <td style={{ padding: 8 }}>{row.person}</td>
                    <td style={{ padding: 8 }}>{row.type}</td>
                    <td style={{ padding: 8 }}>{row.kind}</td>
                    <td style={{ padding: 8 }}>
                      {row.period_start} to {row.period_end}
                    </td>
                    <td style={{ padding: 8 }}>${row.gross}</td>
                    <td style={{ padding: 8 }}>${row.deductions}</td>
                    <td style={{ padding: 8 }}>${row.net}</td>
                    <td style={{ padding: 8 }}>{row.status}</td>
                    <td style={{ padding: 8 }}>
                      {row.approval_recorded_at ?? 'Not recorded'}
                    </td>
                    <td style={{ padding: 8 }}>
                      {row.payment_recorded_at ?? 'Not recorded'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}