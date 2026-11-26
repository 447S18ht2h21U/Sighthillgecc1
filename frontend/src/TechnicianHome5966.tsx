type Props = {
  onAssignedJobs: () => void;
  onInstallation: () => void;
  onPayroll: () => void;
};

export function TechnicianHome5966({
  onAssignedJobs,
  onInstallation,
  onPayroll,
}: Props) {
  const actions = [
    {
      title: 'My assigned jobs',
      detail: 'View your authorized projects and installation details.',
      action: onAssignedJobs,
    },
    {
      title: 'Installation and work completion',
      detail: 'Open installation records and available work functions.',
      action: onInstallation,
    },
    {
      title: 'My payroll',
      detail: 'Open your personal payroll workspace preview.',
      action: onPayroll,
    },
  ];

  return (
    <section
      className="sales-home-5960b technician-home-5966"
      aria-label="Technician Home">

      <h2>What would you like to do?</h2>

      <div className="technician-home-grid-5966">
        {actions.map(item => (
          <button type="button"
            className="sales-home-card-5960b"
            key={item.title}
            onClick={item.action}>
            <span className="technician-action-content-5966">
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </span>
            <span aria-hidden="true"
              className="technician-action-arrow-5966">
              &#8250;
            </span>
          </button>
        ))}
      </div>

      <details className="technician-work-guide-5966">
        <summary>Typical installation workflow</summary>
        <ol>
          <li>Open your assigned project.</li>
          <li>Review the address, equipment and Scope of Work.</li>
          <li>Check the installation authorization.</li>
          <li>Record equipment and work details using available controls.</li>
          <li>Submit completed work for Installation Manager review when enabled.</li>
        </ol>
        <p>Do not begin work until the required authorization is confirmed.</p>
      </details>
    </section>
  );
}
