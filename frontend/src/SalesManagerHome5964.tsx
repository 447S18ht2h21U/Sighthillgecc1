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
  customer: string;
  customer_name?: string;
  state: string;
  reviewer?: string;
  pending?: {
    status: string;
    snapshot?: { customer?: string };
  } | null;
};

type ProjectPage = {
  results: Project[];
  next: string | null;
};

type Props = {
  api: API;
  actorId: string;
  customerNames: Record<string, string>;
  onManageSales: () => void;
  onProjectStatus: () => void;
  onCustomers: () => void;

  onPayroll: () => void;
  onOpenProject: (id: string) => void;
};

export function SalesManagerHome5964({
  api,
  actorId,
  customerNames,
  onManageSales,
  onProjectStatus,
  onCustomers,

  onPayroll,
  onOpenProject,
}: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [reviewOnly, setReviewOnly] = useState(false);

  useEffect(() => {
    let active = true;

    async function loadProjects() {
      try {
        const found: Project[] = [];
        const seen = new Set<string>();
        let page = 1;

        while (true) {
          if (page > 100) {
            throw new Error(
              'The project list exceeds the current review limit. Use Manage sales.'
            );
          }

          const result = await api<ProjectPage>(
            'projects/?sort=NEWEST&page=' + page
          );

          if (!active) return;

          for (const project of result.results) {
            if (!seen.has(project.id)) {
              seen.add(project.id);
              found.push(project);
            }
          }

          if (!result.next) break;
          page++;
        }

        if (active) setProjects(found);
      } catch (err) {
        if (active) {
          setError((err as Error).message);
          setProjects([]);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadProjects();

    return () => { active = false; };
  }, [api, revision, actorId]);

  const awaitingReview = projects.filter(project =>
    project.state !== 'CANCELLED' &&
    project.reviewer === actorId &&
    (
      project.pending?.status === 'SUBMITTED' ||
      project.state === 'SUBMITTED'
    )
  );

  const visibleProjects = reviewOnly
    ? awaitingReview
    : projects.slice(0, 5);

  const actions = [
    {
      title: 'Sales awaiting review',
      detail: loading
        ? 'Loading submitted sales...'
        : error
          ? 'Review list unavailable. Use Manage sales.'
          : awaitingReview.length + ' assigned sales awaiting review.',
      action: () => setReviewOnly(true),
    },
    {
      title: 'Manage sales',
      detail: 'Find and review existing sales projects.',
      action: onManageSales,
    },
    {
      title: 'Project status',
      detail: 'Check project progress and outstanding tasks.',
      action: onProjectStatus,
    },
    {
      title: 'Manage customers',
      detail: 'Review and update customer information.',
      action: onCustomers,
    },

    {
      title: 'Payroll',
      detail: 'Open personal and team payroll previews.',
      action: onPayroll,
    },
  ];

  return (
    <section className="sales-home-5960b manager-home-5964"
      aria-label="Sales Manager Home">

      <h2>What would you like to do?</h2>

      <div className="sales-home-grid-5960b">
        {actions.map(item => (
          <button type="button"
            className="sales-home-card-5960b"
            key={item.title}
            onClick={item.action}
            aria-pressed={
              item.title === 'Sales awaiting review'
                ? reviewOnly : undefined
            }>
            <strong>{item.title}</strong>
            <span>{item.detail}</span>
          </button>
        ))}
      </div>

      <div className="sales-recent-heading-5960b">
        <h2>{reviewOnly
          ? 'Sales awaiting review'
          : 'Recent sales projects'}</h2>

        <div className="manager-list-actions-5964">
          <button type="button" className="quiet"
            onClick={() => setReviewOnly(value => !value)}>
            {reviewOnly
              ? 'Show recent projects'
              : 'Show sales awaiting review'}
          </button>

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
      </div>

      {loading && <p role="status">Loading sales projects...</p>}

      {error && <p role="alert" className="error">{error}</p>}

      {!loading && !error && visibleProjects.length === 0 &&
        <p>{reviewOnly
          ? 'No assigned submitted sales found in the available project list.'
          : 'No projects to display.'}</p>}

      {!loading && !error && visibleProjects.map(project => (
        <div className="sales-recent-project-5960b"
          key={project.id}>
          <div>
            <h3>{
              customerNames[project.customer] ||
              project.customer_name ||
              project.pending?.snapshot?.customer ||
              'Customer name unavailable'
            }</h3>

            <p>{project.location}</p>
            <p className="muted">{project.code}</p>

            <p className="sales-status-5960b">
              {project.pending?.status === 'SUBMITTED' ||
                project.state === 'SUBMITTED'
                ? 'Submitted - review required'
                : project.state.replaceAll('_', ' ')}
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
