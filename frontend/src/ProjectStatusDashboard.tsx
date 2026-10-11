import React, { useEffect, useState } from 'react';

type DashboardProject = {
  id: string;
  code: string;
  customer_name: string;
  location: string;
  state: string;
  payments?: {
    deposit: string;
    final: string;
    full: string;
  };
};

type DashboardStage = {
  key: string;
  name: string;
  count: number;
  projects: DashboardProject[];
};

type DashboardResponse = {
  stages: DashboardStage[];
};

export function ProjectStatusDashboard() {
  const [stages, setStages] = useState<DashboardStage[]>([]);
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/project-dashboard/', {
        credentials: 'same-origin',
        cache: 'no-store',
      });

      if (!response.ok) {
        throw new Error(`Dashboard request failed (${response.status}).`);
      }

      const data: DashboardResponse = await response.json();
      setStages(data.stages);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load dashboard.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section className="project-status-dashboard">
      <div className="title">
        <div>
          <p className="eyebrow">PROJECT OPERATIONS</p>
          <h2>Project Status Dashboard</h2>
          <p className="muted">
            Each stage lists its qualifying projects. Projects may appear in more than one stage.
          </p>
        </div>
        <button className="quiet" type="button" onClick={() => void refresh()} disabled={loading}>
          Refresh dashboard
        </button>
      </div>

      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p>Loading project stages...</p>}

      {!loading && !error && (
        <>
          <div className="dashboard-stage-grid">
            {stages.map(stage => (
              <section key={stage.key} className={`dashboard-stage dashboard-stage-with-projects${selectedStage === stage.key ? " dashboard-stage-selected" : ""}`} role="button" tabIndex={0} aria-expanded={selectedStage === stage.key} onClick={() => setSelectedStage(current => current === stage.key ? null : stage.key)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedStage(current => current === stage.key ? null : stage.key); } }}>
                <span>{stage.name}</span>
                <strong>{stage.count}</strong>
                <small>{stage.count === 1 ? 'project' : 'projects'}</small>
                <div className="dashboard-stage-projects" hidden={selectedStage !== stage.key}>
                  {stage.projects.length === 0 ? (
                    <p className="muted">No projects in this stage.</p>
                  ) : (
                    <ul>
                      {stage.projects.map(project => (
                        <li key={project.id}>
                          <strong>{project.code}</strong>
                          <span>{project.customer_name}</span>
                          <span>{project.location}</span>
                          {stage.key === 'payment_received' && project.payments && (
                            <div className="dashboard-payment-breakdown">
                              <span>Deposit: ${Number(project.payments.deposit).toFixed(2)}</span>
                              <span>Final payment: ${Number(project.payments.final).toFixed(2)}</span>
                              <span>Full payment: ${Number(project.payments.full).toFixed(2)}</span>
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
