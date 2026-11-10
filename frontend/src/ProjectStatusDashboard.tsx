import React, { useEffect, useState } from 'react';
import { ProjectDocumentWorkflowStatus } from './ProjectDocumentWorkflowStatus';
import { CompletionPreflightReview4586 } from './CompletionPreflightReview4586';

type DashboardProject = {
  workflow_evidence?: import('./ProjectDocumentWorkflowStatus').ProjectWorkflowEvidence;
  id: string;
  code: string;
  customer_name: string;
  location: string;
  state: string;
  guidance?: {
    label: string;
    detail: string;
    read_only: boolean;
  };
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
  needs_attention?: DashboardProject[];
};

export function ProjectStatusDashboard({ onOpenProject, onReviewInstallation, onBack, backLabel }: { onOpenProject?: (id: string) => Promise<void>; onReviewInstallation?: (id: string) => void; onBack: () => void; backLabel: string }) {
  const [stages, setStages] = useState<DashboardStage[]>([]);
  const [needsAttention, setNeedsAttention] = useState<DashboardProject[]>([]);
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
      setNeedsAttention(Array.isArray(data.needs_attention) ? data.needs_attention : []);
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
        <div className="dashboard-navigation-actions">
          <button
            className="veridian-dashboard-back"
            type="button"
            onClick={onBack}
          >
            {backLabel}
          </button>
          <button className="quiet" type="button" onClick={() => void refresh()} disabled={loading}>
            Refresh dashboard
          </button>
        </div>
      </div>

      <div className="veridian-guide-banner veridian-guide-banner--info">
        <strong>Project Status Dashboard - How to use this screen</strong>
        <p><strong>Step 1 - Choose a stage.</strong> Select a stage to see the projects listed there. Select it again to close the list.</p>
        <p><strong>Step 2 - Read the project list.</strong> Check the project number, customer name, and installation address. A project may appear in more than one stage.</p>
        <p><strong>Step 3 - Check payments.</strong> In Payment Received, deposits, final payments, and full payments are shown separately.</p>
        <p><strong>Step 4 - Refresh or return.</strong> Select Refresh dashboard to load updated information. Select {backLabel} to leave this screen.</p>
      </div>      {error && <p role="alert" className="error">{error}</p>}
      {loading && <p>Loading project stages...</p>}

      {!loading && !error && (
        <section className="dashboard-attention" aria-labelledby="dashboard-attention-heading">
          <h3 id="dashboard-attention-heading">
            Projects Needing Attention ({needsAttention.length})
          </h3>
          <p className="muted">
            These projects have not earned a Dashboard milestone yet.
            Only projects you are authorized to see are listed here.
          </p>
          {needsAttention.length === 0 ? (
            <p>No projects currently need attention in this section.</p>
          ) : (
            <ul className="dashboard-attention-projects">
              {needsAttention.map(project => (
                <li key={project.id}>
                  <strong>{project.code}</strong>
                  <span>{project.customer_name}</span>
                  <span>{project.location}</span>
                  <ProjectDocumentWorkflowStatus projectCode={project.code} evidence={project.workflow_evidence} />
                  <CompletionPreflightReview4586 projectId={project.id} projectCode={project.code} />
                  {onReviewInstallation && (
                    <button className="quiet" type="button" onKeyDown={event => event.stopPropagation()} onClick={event => {
                      event.stopPropagation();
                      onReviewInstallation(project.id);
                    }} aria-label={`Review installation readiness for ${project.code}`}>Review installation readiness</button>
                  )}
                  {onOpenProject && (
                    <button className="quiet" type="button" onKeyDown={event => event.stopPropagation()} onClick={event => {
                      event.stopPropagation();
                      void onOpenProject(project.id);
                    }} aria-label={`Open project ${project.code}`}>Open project</button>
                  )}
                  {project.guidance?.read_only === true && (
                    <div className="dashboard-next-action">
                      <strong>Suggested next step: {project.guidance.label}</strong>
                      <span>{project.guidance.detail}</span>
                      <small>Guidance only. This does not grant permission or confirm completion.</small>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}


      {!loading && !error && (
        <>
          <div className="dashboard-stage-grid">
            {stages.map(stage => (
              <section key={stage.key} className={`dashboard-stage dashboard-stage-with-projects${selectedStage === stage.key ? " dashboard-stage-selected" : ""}`} role="button" tabIndex={0} aria-expanded={selectedStage === stage.key} onClick={() => setSelectedStage(current => current === stage.key ? null : stage.key)} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedStage(current => current === stage.key ? null : stage.key); } }}>
                <span>{stage.name}</span>
                <strong>{stage.count}</strong>
                <small>{stage.count === 1 ? 'project' : 'projects'}</small>

              </section>
            ))}
          </div>
        </>
      )}

      {/* VERIDIAN Dashboard Full-Width Layout 3999 */}
      {!loading && !error && selectedStage && (
        <section
          className="dashboard-selected-projects"
          aria-label="Selected milestone projects"
        >
          {stages.filter(stage => stage.key === selectedStage).map(stage => (
            <React.Fragment key={stage.key}>
              <h3>{stage.name} ? {stage.count} {stage.count === 1 ? 'project' : 'projects'}</h3>
              {stage.projects.length === 0 ? (
                <p className="muted">No projects currently meet this milestone.</p>
              ) : (
                <ul className="dashboard-selected-project-list">
                  {stage.projects.map(project => (
                    <li key={project.id}>
                      <div className="dashboard-selected-project-info">
                        <strong>{project.code}</strong>
                        <span>{project.customer_name}</span>
                        <span>{project.location}</span>
                      </div>
                      {project.guidance && (
                        <div className="dashboard-selected-project-guidance">
                          <strong>Suggested next step: {project.guidance.label}</strong>
                          <span>{project.guidance.detail}</span>
                          <small>Guidance only. This does not grant permission or confirm completion.</small>
                        </div>
                      )}
                      <ProjectDocumentWorkflowStatus projectCode={project.code} evidence={project.workflow_evidence} />
                  <CompletionPreflightReview4586 projectId={project.id} projectCode={project.code} />
                      <div className="dashboard-selected-project-actions">
                        {onReviewInstallation && (
                          <button
                            className="quiet"
                            type="button"
                            aria-label={`Review installation readiness for ${project.code}`}
                            onClick={() => onReviewInstallation(project.id)}
                          >
                            Review installation readiness
                          </button>
                        )}
                        {onOpenProject && (
                          <button
                            className="quiet"
                            type="button"
                            aria-label={`Open project ${project.code}`}
                            onClick={() => void onOpenProject(project.id)}
                          >
                            Open project
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </React.Fragment>
          ))}
        </section>
      )}
    </section>
  );
}
