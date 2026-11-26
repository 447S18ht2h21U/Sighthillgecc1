type Activity =
  'readiness' |
  'payments' |
  'scheduling' |
  'equipment' |
  'inspections' |
  'payroll';

export function InstallationManagerHome5968({
  onChoose,
}: {
  onChoose: (activity: Activity) => void;
}) {
  const actions: {
    id: Activity;
    title: string;
    detail: string;
  }[] = [
    {
      id: 'readiness',
      title: 'Installation readiness',
      detail: 'Check projects awaiting installation.',
    },
    {
      id: 'payments',
      title: 'Customer payments',
      detail: 'Review collection responsibilities and payment requirements.',
    },
    {
      id: 'scheduling',
      title: 'Schedule and assign work',
      detail: 'Manage installation dates and technician assignments.',
    },
    {
      id: 'equipment',
      title: 'Equipment and materials',
      detail: 'Review equipment and distributor purchase requirements.',
    },
    {
      id: 'inspections',
      title: 'Inspections and certification',
      detail: 'Inspect completed work and review certification status.',
    },
    {
      id: 'payroll',
      title: 'Payroll',
      detail: 'Open personal and assigned technician payroll previews.',
    },
  ];

  return (
    <section
      className="sales-home-5960b installation-manager-home-5968"
      aria-label="Installation Manager Home">

      <h2>What would you like to do?</h2>

      <div className="sales-home-grid-5960b">
        {actions.map(item => (
          <button
            type="button"
            className="sales-home-card-5960b"
            key={item.id}
            onClick={() => onChoose(item.id)}>
            <strong>{item.title}</strong>
            <span>{item.detail}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

export function InstallationManagerSupport5968({
  activity,
  onReadiness,
  onCatalog,
}: {
  activity: 'payments' | 'equipment';
  onReadiness: () => void;
  onCatalog: () => void;
}) {
  return (
    <section className="installation-manager-support-5968">
      {activity === 'payments' ? <>
        <h2>Customer payments</h2>

        <p>
          Collect the required deposit and final payment according
          to the approved customer agreement.
        </p>

        <div className="installation-manager-notice-5968"
          role="status">
          <strong>Payment recording is not enabled here yet.</strong>
          <p>
            Independent bank verification remains required.
            This workspace does not record or verify customer funds.
          </p>
        </div>

        <h3>Collection workflow</h3>

        <ol>
          <li>Review the approved price and payment terms.</li>
          <li>Confirm the required payment and amount outstanding.</li>
          <li>Receive and record the actual customer payment.</li>
          <li>Submit supporting evidence for independent bank verification.</li>
        </ol>

        <p>
          A final customer Receipt requires verified full payment.
          A deposit alone does not authorize a final Receipt.
        </p>

        <button type="button" onClick={onReadiness}>
          Check installation readiness
        </button>

      </> : <>

        <h2>Equipment and materials</h2>

        <p>
          Confirm that equipment and materials purchased match
          the approved project requirements.
        </p>

        <div className="installation-manager-notice-5968"
          role="status">
          <strong>Distributor receipt uploads are not enabled here yet.</strong>
          <p>
            Project-linked receipt capture, purchase verification
            and actual-cost integration remain pending.
          </p>
        </div>

        <h3>Purchase verification workflow</h3>

        <ol>
          <li>Review the approved equipment and materials.</li>
          <li>Retain the original distributor receipt or invoice.</li>
          <li>Check the brand, model, serial numbers and actual cost.</li>
          <li>Confirm that the purchase matches the project.</li>
        </ol>

        <p>
          Purchase evidence does not establish that equipment
          was actually installed.
        </p>

        <button type="button" onClick={onReadiness}>
          Review installation requirements
        </button>

        <button type="button" className="quiet"
          onClick={onCatalog}>
          Manage Equipment Catalog
        </button>

      </>}
    </section>
  );
}
