import React, { useEffect, useState } from 'react';

type Api = <T,>(path: string, method?: string, data?: unknown) => Promise<T>;
type Project = {
  id: string;
  code: string;
  customer_name: string;
  location: string;
};
type Manager = {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
};
type Schedule = {
  id: string;
  project: string;
  scheduled_date: string;
  installation_manager: string;
  status: string;
};
type Page<T> = {
  results: T[];
  next: string | null;
};

type InstallationReadiness = {
  project_id: string;
  eligible: boolean;
  requirements: {
    approved_msr: boolean;
    contract_signed: boolean;
    invoice_signed: boolean;
    cancellation_complete: boolean;
    waiting_period_complete: boolean;
    deposit_verified: boolean;
  };
  blocking_reasons: string[];
};

export function InstallationScheduling({
  api,
  selectedProjectId,
  onReturnToProject,
  onProjectSelected,
}: {
  api: Api;
  selectedProjectId?: string;
  onReturnToProject: () => void;
  onProjectSelected: (projectId: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [projectId, setProjectId] = useState('');
  const [readiness, setReadiness] = useState<InstallationReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [readinessError, setReadinessError] = useState('');
  const [managerId, setManagerId] = useState('');
  const [scheduledDate, setScheduledDate] = useState('');
  const [canManage, setCanManage] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function readPages<T>(path: string): Promise<T[]> {
    const all: T[] = [];
    let page = 1;
    while (true) {
      const result = await api<Page<T>>(`${path}?page=${page}`);
      all.push(...result.results);
      if (!result.next) return all;
      page += 1;
    }
  }

  async function refresh() {
    const [visibleProjects, visibleSchedules] = await Promise.all([
      readPages<Project>('operational-projects/'),
      readPages<Schedule>('installation-schedules/'),
    ]);
    setProjects(visibleProjects);
    setSchedules(visibleSchedules);
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const [visibleProjects, visibleSchedules] = await Promise.all([
          readPages<Project>('operational-projects/'),
          readPages<Schedule>('installation-schedules/'),
        ]);
        if (!active) return;
        setProjects(visibleProjects);
        setSchedules(visibleSchedules);
        try {
          const eligible = await api<Manager[]>('installation-managers/');
          if (active) {
            setManagers(eligible);
            setCanManage(true);
          }
        } catch {
          if (active) setCanManage(false);
        }
      } catch (err) {
        if (active) setError((err as Error).message);
      }
    })();
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    let active = true;

    setReadiness(null);
    setReadinessError('');
    setReadinessLoading(Boolean(projectId));

    if (projectId) {
      void api<InstallationReadiness>(
        `operational-projects/${projectId}/installation-eligibility/`
      ).then(result => {
        if (active) {
          setReadiness(result);
          setReadinessLoading(false);
        }
      }).catch(err => {
        if (active) {
          setReadinessError((err as Error).message);
          setReadinessLoading(false);
        }
      });
    }

    return () => { active = false; };
  }, [api, projectId]);

  async function perform(action: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await action();
      await refresh();
      setMessage('Installation schedule updated.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const projectNames = new Map(projects.map(project => [
    project.id, `${project.code} - ${project.customer_name}`,
  ]));
  const managerNames = new Map(managers.map(manager => [
    manager.id,
    `${manager.first_name} ${manager.last_name}`.trim() || manager.username,
  ]));

  return <section>
    <div className="title">
      <div>
        <p className="eyebrow">VERIDIAN / OPERATIONS</p>
        <h2>Installation Scheduling</h2>
        <p className="muted">Schedules for projects within your authorized operational scope.</p>
      </div>
      <button type="button" className="quiet" disabled={busy}
        onClick={() => void perform(refresh)}>Refresh</button>
    </div>

    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status">{message}</p>}

    {canManage && <form onSubmit={event => {
      event.preventDefault();
      void perform(async () => {
        await api('installation-schedules/', 'POST', {
          project: projectId,
          scheduled_date: scheduledDate,
          installation_manager: managerId,
        });
        setProjectId('');
        setManagerId('');
        setScheduledDate('');
      });
    }}>
      <h3>Schedule an installation</h3>
      <div className="grid">
        <label>Project
          <select required value={projectId} onChange={event => {
            const id = event.target.value;
            setProjectId(id);
            if (id) onProjectSelected(id);
          }}>
            <option value="">Choose project</option>
            {projects.map(project => <option key={project.id} value={project.id}>
              {project.code} - {project.customer_name}
            </option>)}
          </select>
        </label>
        {projectId && <div className="installation-readiness" role="status" aria-live="polite">
          <h4>Installation Readiness</h4>
          {readinessLoading
            ? <p>Checking installation requirements...</p>
            : readinessError
              ? <p className="error">Unable to verify readiness: {readinessError}</p>
              : readiness
                ? <>
                    <p><strong>{readiness.eligible ? 'READY FOR INSTALLATION' : 'NOT READY FOR INSTALLATION'}</strong></p>
                    <p className="muted">
                      {readiness.eligible
                        ? 'All requirements satisfied.'
                        : `${Object.values(readiness.requirements).filter(value => !value).length} readiness requirements are incomplete.`}
                    </p>
                    <ul>
                      {([
                        ['approved_msr', 'Approved Master Sales Record'],
                        ['contract_signed', 'Contract signed'],
                        ['invoice_signed', 'Invoice signed'],
                        ['cancellation_complete', 'Cancellation requirement complete'],
                        ['waiting_period_complete', 'Five-calendar-day waiting period complete'],
                        ['deposit_verified', 'Deposit verified or not required'],
                      ] as const).map(([key, label]) =>
                        <li key={key}>
                          {readiness.requirements[key]
                            ? 'COMPLETE'
                            : 'MISSING'}: {label}
                        </li>
                      )}
                    </ul>
                    {readiness.blocking_reasons.length > 0 && <>
                      <p><strong>Scheduling blocked because:</strong></p>
                      <ul>{readiness.blocking_reasons.map((reason, index) =>
                        <li key={index}>{reason}</li>
                      )}</ul>
                    </>}
                  </>
                : <p>Readiness information is unavailable.</p>}
        </div>}
        <label>Installation date
          <input required type="date" value={scheduledDate}
            onChange={event => setScheduledDate(event.target.value)}/>
        </label>
        <label>Installation Manager
          <select required value={managerId} onChange={event => setManagerId(event.target.value)}>
            <option value="">Choose manager</option>
            {managers.map(manager => <option key={manager.id} value={manager.id}>
              {managerNames.get(manager.id)}
            </option>)}
          </select>
        </label>
      </div>
      <button disabled={
        busy ||
        readinessLoading ||
        Boolean(readinessError) ||
        !readiness?.eligible ||
        readiness.project_id !== projectId ||
        !projectId ||
        !scheduledDate ||
        !managerId
      }>Create schedule</button>
      <p className="muted">Scheduling eligibility must be independently verified; a schedule status is not proof of signed completion.</p>
    </form>}

    <h3>Installation schedules</h3>
    {schedules.length === 0
      ? <p className="muted">No installation schedules are visible.</p>
      : <table>
          <thead><tr>
            <th>Project</th><th>Date</th><th>Manager</th><th>Status</th><th>Actions</th>
          </tr></thead>
          <tbody>{schedules.map(schedule => <tr key={schedule.id}>
            <td>{projectNames.get(schedule.project) || schedule.project}</td>
            <td>{schedule.scheduled_date}</td>
            <td>{managerNames.get(schedule.installation_manager) || 'Assigned manager'}</td>
            <td>{schedule.status.replaceAll('_', ' ')}</td>
            <td>{canManage && schedule.status === 'SCHEDULED'
              ? <div className="actions">
                  <button type="button" disabled={busy}
                    onClick={() => void perform(() =>
                      api(`installation-schedules/${schedule.id}/complete/`, 'POST', {}))}>
                    Mark operationally complete
                  </button>
                  <button type="button" className="quiet" disabled={busy}
                    onClick={() => void perform(() =>
                      api(`installation-schedules/${schedule.id}/cancel/`, 'POST', {}))}>
                    Cancel
                  </button>
                </div>
              : '-'}</td>
          </tr>)}</tbody>
        </table>}
    {schedules.some(schedule => schedule.status === 'COMPLETED') && (
      <div className="installation-completion-guidance">
        <p><strong>Installation completed operationally.</strong></p>
        {selectedProjectId && <button
          type="button"
          className="quiet"
          onClick={onReturnToProject}
        >
          Return to Project Workspace
        </button>}
        <p>Next steps:</p>
        <ul>
          <li>Record verified work completion evidence.</li>
          <li>Prepare the completion certificate.</li>
          <li>Complete release review and approval.</li>
        </ul>
      </div>
    )}

    <p className="muted">Operational completion alone does not satisfy the dashboard's signed completion certificate requirement.</p>
  </section>;
}
