import React, { useEffect, useRef, useState } from 'react';
import { InstallationInspectionEntry4843 } from './InstallationInspectionEntry4843';

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
  installation_manager_display: string;
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
    cancellation_complete: boolean;
    waiting_period_complete: boolean;
    deposit_verified: boolean;
  };
  blocking_reasons: string[];
  expedited_service?: {
    status: string;
    storage_available: boolean;
    attempt_recorded: boolean;
    documents_retained: boolean;
    retained_document_count: number;
    provider_authenticated: boolean;
    signatures_verified: boolean;
    distribution_verified: boolean;
    expedited_authorized: boolean;
    installation_authorized: boolean;
  };
  installation_start?: {
    project_id: string;
    schedule_verified: boolean;
    commercial_ready: boolean;
    trusted_equipment_verified: boolean;
    expedited_authorized: boolean;
    installation_authorized: boolean;
    installation_started: boolean;
    blockers: string[];
  };
};

type ProposedDateAssessment = {
  project_id: string;
  scheduled_date: string;
  normal_date_eligible: boolean;
  payment_ready: boolean;
  scheduling_candidate: boolean;
  earliest_normal_installation_at: string;
  payment_explanation: string;
  installation_authorized: boolean;
  installation_started: boolean;
  expedited_authorized: boolean;
};

export function InstallationScheduling({
  api,
  actorId,
  actorRole,
  selectedProjectId,
  onReturnToProject,
  onProjectSelected,
}: {
  api: Api;
  actorId: string;
  actorRole: string;
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
  const [scheduleFeedback, setScheduleFeedback] = useState<{
    status: 'working' | 'success' | 'error';
    message: string;
  } | null>(null);
  const [pendingStatusAction, setPendingStatusAction] = useState<{
    scheduleId: string;
    projectId: string;
    kind: 'complete' | 'cancel';
  } | null>(null);
  const readinessRequestId = useRef(0);
  const selectedProjectRef = useRef(projectId);
  useEffect(() => {
    if (!selectedProjectId) return;
    selectedProjectRef.current = selectedProjectId;
    readinessRequestId.current += 1;
    setReadiness(null);
    setReadinessError('');
    setProjectId(selectedProjectId);
  }, [selectedProjectId]);

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
    const requestedProject = selectedProjectRef.current;
    const requestId = ++readinessRequestId.current;
    const isCurrent = () =>
      requestId === readinessRequestId.current &&
      requestedProject === selectedProjectRef.current;

    setReadiness(null);
    setReadinessError('');
    setReadinessLoading(Boolean(requestedProject));

    try {
      const [visibleProjects, visibleSchedules, currentReadiness] = await Promise.all([
        readPages<Project>('operational-projects/'),
        readPages<Schedule>('installation-schedules/'),
        requestedProject
          ? api<InstallationReadiness>(
              `operational-projects/${requestedProject}/installation-eligibility/`
            )
          : Promise.resolve(null),
      ]);

      setProjects(visibleProjects);
      setSchedules(visibleSchedules);
      setPendingStatusAction(current =>
        current && visibleSchedules.some(schedule =>
          schedule.id === current.scheduleId &&
          schedule.project === current.projectId &&
          schedule.status === 'SCHEDULED'
        ) ? current : null
      );

      if (isCurrent()) {
        setReadiness(
          currentReadiness?.project_id === requestedProject
            ? currentReadiness
            : null
        );
      }
    } catch (err) {
      if (isCurrent()) {
        setReadiness(null);
        setReadinessError((err as Error).message);
      }
      throw err;
    } finally {
      if (isCurrent()) {
        setReadinessLoading(false);
      }
    }
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
    selectedProjectRef.current = projectId;
    const requestId = ++readinessRequestId.current;
    const isCurrent = () =>
      active &&
      requestId === readinessRequestId.current &&
      selectedProjectRef.current === projectId;

    setReadiness(null);
    setReadinessError('');
    setReadinessLoading(Boolean(projectId));

    if (projectId) {
      void api<InstallationReadiness>(
        `operational-projects/${projectId}/installation-eligibility/`
      ).then(result => {
        if (isCurrent()) {
          setReadiness(result.project_id === projectId ? result : null);
          setReadinessLoading(false);
        }
      }).catch(err => {
        if (isCurrent()) {
          setReadinessError((err as Error).message);
          setReadinessLoading(false);
        }
      });
    }

    return () => { active = false; };
  }, [api, projectId]);

  async function perform(
    action: () => Promise<unknown>,
    successMessage = 'Installation schedule updated.',
    scope: 'general' | 'schedule' = 'general',
  ) {
    if (busy) return;
    setBusy(true);
    setError('');
    setMessage('');
    if (scope === 'schedule') {
      setScheduleFeedback({
        status: 'working',
        message: 'Checking the proposed installation date...',
      });
    }
    try {
      await action();
      try {
        await refresh();
      } catch {
        // Do not report a completed write as failed just because
        // the subsequent list refresh was unsuccessful.
        setMessage(
          'The action was accepted, but the updated schedule list could not be refreshed.'
        );
        if (scope === 'schedule') {
          setScheduleFeedback({
            status: 'success',
            message: 'Appointment created. Refresh the list to verify its details.',
          });
        }
        return;
      }
      setMessage(successMessage);
      if (scope === 'schedule') {
        setScheduleFeedback({
          status: 'success',
          message: successMessage,
        });
      }
    } catch (err) {
      const explanation = err instanceof Error
        ? err.message : 'Installation operation failed.';
      setError(explanation);
      if (scope === 'schedule') {
        setScheduleFeedback({
          status: 'error',
          message: `Appointment not confirmed: ${explanation}`,
        });
      }
    } finally {
      setBusy(false);
    }
  }

  const projectNames = new Map(projects.map(project => [
    project.id, `${project.code} - ${project.customer_name}`,
  ]));
  const managerNames = new Map(managers.map(manager => [
    manager.id,
    `${manager.first_name} ${manager.last_name}`.trim() ? `${`${manager.first_name} ${manager.last_name}`.trim()} (${manager.username})` : manager.username,
  ]));

  return <section>
    <div className="title">
      <div>
        <p className="muted">Choose a project to check whether it is ready for installation. You can also review installation schedules for projects you are allowed to see.</p>
      </div>
      <button type="button" className="quiet" disabled={busy}
        onClick={() => void perform(async () => undefined, 'Installation information refreshed.')}>Refresh installation status</button>
    </div>

    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status">{message}</p>}

    {canManage && <form onSubmit={event => {
      event.preventDefault();
      void perform(async () => {
        const requestedProject = projectId;
        const requestedDate = scheduledDate;
        const requestedManager = managerId;
        const requestId = ++readinessRequestId.current;

        setReadiness(null);
        setReadinessError('');
        setReadinessLoading(true);

        let current: InstallationReadiness;

        try {
          current = await api<InstallationReadiness>(
            `operational-projects/${requestedProject}/installation-eligibility/`
          );
        } catch (err) {
          if (
            requestId === readinessRequestId.current &&
            selectedProjectRef.current === requestedProject
          ) {
            setReadiness(null);
            setReadinessError((err as Error).message);
            setReadinessLoading(false);
          }
          throw err;
        }

        if (
          requestId !== readinessRequestId.current ||
          selectedProjectRef.current !== requestedProject
        ) {
          throw new Error('The selected project changed. Review readiness and try again.');
        }

        if (current.project_id !== requestedProject) {
          setReadiness(null);
          setReadinessError('Readiness information did not match the selected project.');
          setReadinessLoading(false);
          throw new Error('Readiness could not be verified for the selected project.');
        }

        setReadiness(current);
        setReadinessLoading(false);

        // Current-time readiness and proposed future-date eligibility
        // are different assessments. The server is authoritative.
        setScheduleFeedback({
          status: 'working',
          message: 'Assessing date, payment and verified waiting period...',
        });

        const assessment = await api<ProposedDateAssessment>(
          'installation-schedules/assess-proposed-date/',
          'POST',
          {
            project: requestedProject,
            scheduled_date: requestedDate,
          },
        );

        if (
          assessment.project_id !== requestedProject ||
          assessment.scheduled_date !== requestedDate
        ) {
          throw new Error(
            'The date assessment did not match the selected project and date.'
          );
        }

        if (
          assessment.installation_authorized ||
          assessment.installation_started ||
          assessment.expedited_authorized
        ) {
          throw new Error(
            'Unexpected installation authorization in the date assessment.'
          );
        }

        if (
          !assessment.scheduling_candidate ||
          !assessment.normal_date_eligible ||
          !assessment.payment_ready
        ) {
          throw new Error(
            !assessment.normal_date_eligible
              ? `Proposed date is too early. Normal eligibility begins ${assessment.earliest_normal_installation_at}.`
              : assessment.payment_explanation ||
                'Required payment evidence is incomplete.'
          );
        }

        if (
          requestId !== readinessRequestId.current ||
          selectedProjectRef.current !== requestedProject
        ) {
          throw new Error(
            'The project changed during assessment. Please review it again.'
          );
        }

        setScheduleFeedback({
          status: 'working',
          message: 'Date approved for scheduling. Creating appointment...',
        });

        await api('installation-schedules/schedule-future/', 'POST', {
          project: requestedProject,
          scheduled_date: requestedDate,
          installation_manager: requestedManager,
        });

        if (selectedProjectRef.current === requestedProject) {
          selectedProjectRef.current = '';
          readinessRequestId.current += 1;
          setProjectId('');
          setManagerId('');
          setScheduledDate('');
          setReadiness(null);
        }
      },
        'Installation appointment created. Installation start is not authorized.',
        'schedule',
      );
    }}>
      <h3>Schedule an installation</h3>
      <div className="grid">
        <label>Project
          <select required value={projectId} onChange={event => {
            const id = event.target.value;
            selectedProjectRef.current = id;
            readinessRequestId.current += 1;
            setReadiness(null);
            setReadinessError('');
            setReadinessLoading(Boolean(id));
            setProjectId(id);
            if (id) onProjectSelected(id);
          }}>
            <option value="">Choose project</option>
            {projects.map(project => <option key={project.id} value={project.id}>
              {project.code} - {project.customer_name}
            </option>)}
          </select>
        </label>
        {projectId && <div className="installation-readiness">
          <div className="installation-readiness-summary" role="status" aria-live="polite">
            <h4>Installation Readiness — Current Assessment</h4>
            {readinessLoading
              ? <p>Checking current project requirements...</p>
              : readinessError
                ? <p role="alert">Evidence could not be verified. Scheduling approval has not been established.</p>
                : readiness
                  ? <>
                      <p><strong>
                        {readiness.eligible
                          ? 'Current scheduling requirements satisfied'
                          : 'Requirements still outstanding'}
                      </strong></p>
                      {readiness.blocking_reasons.length > 0
                        ? <ul>{readiness.blocking_reasons.map((blocker, index) =>
                            <li key={index}>{blocker}</li>
                          )}</ul>
                        : <p>No current-time scheduling blockers reported.</p>}
                    </>
                  : <p>Readiness has not been established.</p>}
            <p className="muted">
              A proposed future date receives a separate server assessment.
              This summary does not authorize installation to start.
            </p>
          </div>
          {readiness && !readiness.eligible && (
            <div className="installation-evidence-guidance">
              <strong>How to resolve outstanding evidence</strong>
              <p>
                <strong>Cancellation deadline:</strong> The authorized
                Comptroller can review the approved MSR's Project
                verification evidence section in the customer/project
                workspace. Recording an attestation does not substitute
                for reviewing the referenced evidence.
              </p>
              <p>
                <strong>Customer deposit:</strong> The authorized payment
                workflow must establish verified payment and bank
                confirmation. Do not mark funds received merely to
                clear a scheduling blocker.
              </p>
              <p>
                After evidence is recorded and verified, select
                Refresh installation status to obtain a new assessment.
              </p>
            </div>
          )}
          <details className="installation-readiness-details">
            <summary>View detailed readiness and installation-start safeguards</summary>
            <h4>Installation Readiness Details</h4>
          {readiness?.installation_start && (
            <div className="installation-start-readiness">
              <h4>Installation Start Authorization</h4>
              <p>
                <strong>Not authorized to begin installation</strong>
              </p>
              <p>
                Schedule verified: {readiness.installation_start.schedule_verified ? 'Yes' : 'No'}
              </p>
              <p>
                Commercial readiness: {readiness.installation_start.commercial_ready ? 'Verified' : 'Not verified'}
              </p>
              <p>
                Trusted equipment verification: {readiness.installation_start.trusted_equipment_verified ? 'Verified' : 'Pending'}
              </p>
              <p>
                Expedited authorization: {readiness.installation_start.expedited_authorized ? 'Reported' : 'Not verified'}
              </p>
              {readiness.installation_start.blockers.length > 0 && (
                <ul>
                  {readiness.installation_start.blockers.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              )}
              <p className="muted">
                Current-time assessment only. No installation-start action
                is available or authorized.
              </p>
            </div>
          )}
          {readiness?.expedited_service && (
            <div className="expedited-service-status">
              <h4>Expedited Service Evidence</h4>
              <p>
                {!readiness.expedited_service.storage_available
                  ? 'Expedited evidence storage unavailable. Database migration and verification are pending.'
                  : readiness.expedited_service.documents_retained
                  ? `${readiness.expedited_service.retained_document_count} candidate documents retained; verification pending.`
                  : readiness.expedited_service.attempt_recorded
                    ? 'Expedited signing attempt recorded; verified document retention pending.'
                    : 'No expedited signing evidence retained for the current approved MSR.'}
              </p>
              <p>
                <strong>Expedited installation authorization: Not verified.</strong>
              </p>
              <p className="muted">
                Retained documents do not establish DocuSign authentication,
                independent approvals, customer distribution, or permission
                to install before applicable waiting and cancellation deadlines.
              </p>
            </div>
          )}
          {readinessLoading
            ? <p>Checking installation requirements...</p>
            : readinessError
              ? <p className="error">Unable to verify readiness: {readinessError}</p>
              : readiness
                ? <>
                    <p><strong>{readiness.eligible ? 'SCHEDULING REQUIREMENTS SATISFIED' : 'SCHEDULING REQUIREMENTS INCOMPLETE'}</strong></p>
                    <p className="muted">No customer Receipt signature is required. Before administrative project completion, the exact final Receipt must be retained and its email delivery evidenced, and GECC must have received and retained a verified completed DocuSign Completion Certificate. The Customer Satisfaction Survey is optional. Scheduling does not authorize installation to start.</p>
                    <p className="muted">
                      {readiness.eligible
                        ? 'All requirements satisfied.'
                        : `${Object.values(readiness.requirements).filter(value => !value).length} readiness requirements are incomplete.`}
                    </p>
                    <ul>
                      {([
                        ['approved_msr', 'Project sales record approved'],
                        ['contract_signed', 'Customer contract signed'],
                        ['cancellation_complete', 'Customer cancellation period has ended'],
                        ['waiting_period_complete', 'Five-calendar-day waiting period has ended'],
                        ['deposit_verified', 'Required customer payment confirmed by the bank'],
                      ] as const).map(([key, label]) =>
                        <li key={key}>
                          {readiness.requirements[key]
                            ? 'COMPLETE'
                            : 'NOT COMPLETE'}: {label}
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
          </details>
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
        !projectId ||
        !scheduledDate ||
        !managerId
      }>Create schedule</button>
      <p className="installation-schedule-help">
        A future appointment is assessed against its proposed date.
        Missing verified evidence cannot be bypassed.
      </p>
      {scheduleFeedback && <p
        role={scheduleFeedback.status === 'error' ? 'alert' : 'status'}
        aria-live="polite"
        className={`installation-action-feedback ${scheduleFeedback.status}`}
      >
        {scheduleFeedback.message}
      </p>}
      <p className="muted">
        The proposed date receives a separate server-side assessment.
        A future appointment does not authorize installation to start.
        Expedited installation requires independently verified evidence.
      </p>
    </form>}

    <h3>Installation schedules</h3>
    {schedules.length === 0
      ? <p className="muted">No installation schedules are visible.</p>
      : <table className="installation-schedules-table">
          <thead><tr>
            <th>Project</th><th>Date</th><th>Manager</th><th>Status</th><th>Actions</th>
          </tr></thead>
          <tbody>{schedules.map(schedule => <tr key={schedule.id}>
            <td>{projectNames.get(schedule.project) || schedule.project}</td>
            <td>{schedule.scheduled_date}</td>
            <td>{schedule.installation_manager_display || 'Assigned manager'}</td>
            <td>{schedule.status.replaceAll('_', ' ')}</td>
            <td>{canManage && schedule.status === 'SCHEDULED'
              ? <div>
                  <div className="actions">
                    <button type="button" disabled={busy}
                      onClick={() => setPendingStatusAction({
                        scheduleId: schedule.id,
                        projectId: schedule.project,
                        kind: 'complete',
                      })}>
                      Mark operationally complete
                    </button>
                    <button type="button" className="quiet" disabled={busy}
                      onClick={() => setPendingStatusAction({
                        scheduleId: schedule.id,
                        projectId: schedule.project,
                        kind: 'cancel',
                      })}>
                      Cancel
                    </button>
                  </div>
                  {pendingStatusAction?.scheduleId === schedule.id &&
                    pendingStatusAction.projectId === schedule.project && (
                    <div role="group" aria-label="Confirm installation status change">
                      <p><strong>
                        {pendingStatusAction.kind === 'complete'
                          ? 'Confirm installation completion'
                          : 'Confirm installation cancellation'}
                      </strong></p>
                      <p><strong>Project:</strong> {projectNames.get(schedule.project) || schedule.project}</p>
                      <p>
                        {pendingStatusAction.kind === 'complete'
                          ? 'This means the installation work is finished. It does not mean the customer has signed the Completion Certificate.'
                          : 'This will cancel the installation schedule. The installation will no longer be scheduled.'}
                      </p>
                      <p>Are you sure you want to continue?</p>
                      <div className="actions">
                        <button type="button" className="quiet" disabled={busy}
                          onClick={() => setPendingStatusAction(null)}>
                          {pendingStatusAction.kind === 'complete'
                            ? 'Go back'
                            : 'Keep installation scheduled'}
                        </button>
                        <button type="button" disabled={busy}
                          onClick={() => {
                            const requested = pendingStatusAction;
                            if (!requested || requested.scheduleId !== schedule.id ||
                                requested.projectId !== schedule.project ||
                                schedule.status !== 'SCHEDULED') return;
                            setPendingStatusAction(null);
                            void perform(() => api(
                              `installation-schedules/${requested.scheduleId}/${requested.kind === 'complete' ? 'complete' : 'cancel'}/`,
                              'POST',
                              {}
                            ));
                          }}>
                          {pendingStatusAction.kind === 'complete'
                            ? 'Confirm completion'
                            : 'Confirm cancellation'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              : '-'}</td>
          </tr>)}</tbody>
        </table>}
    {canManage &&
      actorRole === 'INSTALLATION_MANAGER' &&
      Boolean(actorId) &&
      Boolean(projectId) &&
      schedules.some(
        schedule =>
          schedule.project === projectId &&
          schedule.status === 'COMPLETED' &&
          schedule.installation_manager === actorId
      ) && (
        <InstallationInspectionEntry4843
          key={projectId}
          api={api}
          projectId={projectId}
        />
      )}

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
