import { useEffect, useState } from 'react';

type API = <T>(
  path: string,
  method?: string,
  data?: unknown
) => Promise<T>;

type Project = {
  id: string;
  code: string;
  location: string;
  state: string;
  customer: string;
};

type Props = {
  api: API;
  customerNames: Record<string, string>;
  onStartNew: () => void;
  onFindProjects: () => void;
  onOpenProject: (id: string) => void;
  onCustomers: () => void;
  onProjectStatus: () => void;
  onPayroll: () => void;
};

export function SalesWorkspace5690({
  api, customerNames, onStartNew, onFindProjects,
  onOpenProject, onCustomers, onProjectStatus, onPayroll,
}: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    api<{results: Project[]}>('projects/?sort=NEWEST')
      .then(result => {
        if (active) setProjects(result.results.slice(0, 5));
      })
      .catch(err => {
        if (active) setError((err as Error).message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [api, revision]);

  const actions = [
    {
      title: 'Start new sale',
      detail: 'Find or add a customer and create a project.',
      action: onStartNew,
      primary: true,
    },
    {
      title: 'Continue existing sale',
      detail: 'Find a project or resume unfinished work.',
      action: onFindProjects,
    },
    {
      title: 'Project status',
      detail: 'Check the progress of your projects.',
      action: onProjectStatus,
    },
    {
      title: 'Manage customers',
      detail: 'Find and update customer information.',
      action: onCustomers,
    },
    {
      title: 'My payroll',
      detail: 'View the current payroll workspace preview.',
      action: onPayroll,
    },
  ];

  const statusLabel = (state: string) => {
    if (state === 'DRAFT') return 'Draft - continue preparation';
    if (state === 'SUBMITTED') return 'Submitted - review pending';
    if (state === 'APPROVED') return 'Approved MSR';
    return state.replaceAll('_', ' ');
  };

  return (
    <section className="sales-home-5960b" aria-label="Sales Home">
      <h2>What would you like to do?</h2>

      <div className="sales-home-grid-5960b">
        {actions.map(item => (
          <button
            type="button"
            key={item.title}
            className={
              'sales-home-card-5960b' +
              (item.primary ? ' primary' : '')
            }
            onClick={item.action}
          >
            <strong>{item.title}</strong>
            <span>{item.detail}</span>
          </button>
        ))}
      </div>

      <div className="sales-recent-heading-5960b">
        <h2>My recent projects</h2>
        <button type="button" className="quiet"
          disabled={loading}
          onClick={() => {
            setLoading(true);
            setError('');
            setRevision(value => value + 1);
          }}>
          Refresh
        </button>
      </div>

      {loading && <p role="status">Loading projects...</p>}
      {error && <p role="alert" className="error">{error}</p>}

      {!loading && !error && projects.length === 0 &&
        <p>No projects to display.</p>}

      {!loading && !error && projects.map(project => (
        <div className="sales-recent-project-5960b"
          key={project.id}>
          <div>
            <h3>{customerNames[project.customer] ||
              'Customer name unavailable'}</h3>
            <p>{project.location}</p>
            <p className="muted">{project.code}</p>
            <p className="sales-status-5960b">
              {statusLabel(project.state)}
            </p>
          </div>
          <button type="button" className="quiet"
            onClick={() => onOpenProject(project.id)}>
            Open project
          </button>
        </div>
      ))}
    </section>
  );
}
