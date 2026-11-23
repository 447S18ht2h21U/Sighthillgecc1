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
};

type ProjectPage = {
  results: Project[];
  count: number;
};

export function SalesWorkspace5690({
  api,
  onStartNew,
  onFindProjects,
  onOpenProject,
}: {
  api: API;
  onStartNew: () => void;
  onFindProjects: () => void;
  onOpenProject: (id: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let closed = false;
    void api<ProjectPage>('projects/?sort=NEWEST')
      .then(data => {
        if (!closed) setProjects(data.results.slice(0, 5));
      })
      .catch(err => {
        if (!closed) setError((err as Error).message);
      })
      .finally(() => {
        if (!closed) setLoading(false);
      });

    return () => { closed = true; };
  }, [api]);

  return (
    <section aria-label="Sales Workspace">
      <p>What would you like to do?</p>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))',
        gap: 16,
        marginBottom: 24,
      }}>
        <div style={{
          border: '1px solid #D7E3E7',
          borderRadius: 8,
          padding: 20,
        }}>
          <h2>Start new sale</h2>
          <p>Find or add a customer, then create a project.</p>
          <button type="button" onClick={onStartNew}>
            Start new sale
          </button>
        </div>

        <div style={{
          border: '1px solid #D7E3E7',
          borderRadius: 8,
          padding: 20,
        }}>
          <h2>Continue existing sale</h2>
          <p>Find an existing project or continue a draft.</p>
          <button type="button" onClick={onFindProjects}>
            Find project
          </button>
        </div>
      </div>

      <h2>My projects</h2>
      <p className="muted">
        Your five most recent authorized projects.
      </p>

      {loading && <p role="status">Loading projects...</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {!loading && !error && projects.length === 0 &&
        <p>No projects to display.</p>}

      {projects.map(project => (
        <div key={project.id} style={{
          borderTop: '1px solid #D7E3E7',
          padding: '12px 0',
        }}>
          <button
            type="button"
            className="quiet"
            onClick={() => onOpenProject(project.id)}
          >
            {project.code}
          </button>
          <p>{project.location}</p>
          <p className="muted">Status: {project.state}</p>
        </div>
      ))}
    </section>
  );
}
