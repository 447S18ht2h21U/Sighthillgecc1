import { useEffect, useRef, useState } from 'react';

type Api = <T,>(
  path: string,
  method?: string,
  data?: unknown
) => Promise<T>;

type Page<T> = {
  results: T[];
  next: string | null;
};

type Project = {
  id: string;
  code: string;
  customer_name: string;
  location: string;
  state: string;
};

type Employee = {
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

type Assignment = {
  id: string;
  project: string;
  technical_associate: string;
  technician_username: string;
  technician_first_name: string;
  technician_last_name: string;
  effective_date: string;
  status: string;
};

type Assessment = {
  project_id: string;
  scheduled_date: string;
  normal_date_eligible: boolean;
  payment_ready: boolean;
  scheduling_candidate: boolean;
  payment_explanation: string;
  earliest_normal_installation_at: string;
  installation_authorized: boolean;
  installation_started: boolean;
  expedited_authorized: boolean;
};

type CombinedResult = {
  project_id: string;
  schedule_id: string;
  scheduled_date: string;
  installation_manager_id: string;
  assignments: {
    id: string;
    technician_id: string;
  }[];
  installation_authorized: boolean;
  installation_started: boolean;
};

function employeeName(employee: Employee) {
  return [employee.first_name, employee.last_name]
    .filter(Boolean).join(' ').trim() || employee.username;
}

function technicianName(assignment: Assignment) {
  return [
    assignment.technician_first_name,
    assignment.technician_last_name,
  ].filter(Boolean).join(' ').trim() ||
    assignment.technician_username;
}

function displayDate(value: string) {
  if (!value) return '';
  return new Date(value + 'T12:00:00').toLocaleDateString(
    'en-US',
    { month: 'short', day: 'numeric', year: 'numeric' }
  );
}

export function UnifiedInstallationSchedule5979({
  api,
  actorId,
  actorName,
  initialProjectId = '',
  onReadiness,
  onExistingAssignments,
}: {
  api: Api;
  actorId: string;
  actorName: string;
  initialProjectId?: string;
  onReadiness: (projectId: string) => void;
  onExistingAssignments: () => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [technicians, setTechnicians] = useState<Employee[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [assignments, setAssignments] = useState<
    Record<string, Assignment[]>
  >({});
  const [assignmentErrors, setAssignmentErrors] = useState<
    Record<string, string>
  >({});
  const [projectId, setProjectId] = useState(initialProjectId);
  const [date, setDate] = useState('');
  const [technicianIds, setTechnicianIds] = useState<string[]>([]);
  const [managerEligible, setManagerEligible] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uncertain, setUncertain] = useState(false);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [revision, setRevision] = useState(0);
  const inFlight = useRef(false);

  async function readAll<T>(path: string): Promise<T[]> {
    const result: T[] = [];
    const separator = path.includes('?') ? '&' : '?';

    for (let page = 1; page <= 100; page++) {
      const batch = await api<Page<T>>(
        path + separator + 'page=' + page
      );

      if (!Array.isArray(batch.results)) {
        throw new Error('The server returned an invalid project list.');
      }

      result.push(...batch.results);

      if (!batch.next) return result;
    }

    throw new Error('The record list exceeds the current review limit.');
  }

  useEffect(() => {
    let active = true;

    setLoading(true);
    setLoadError('');
    setManagerEligible(false);

    void (async () => {
      try {
        const [
          projectRows,
          technicianRows,
          scheduleRows,
          managers,
        ] = await Promise.all([
          readAll<Project>('operational-projects/'),
          api<Employee[]>('technicians/'),
          readAll<Schedule>('installation-schedules/'),
          api<Employee[]>('installation-managers/'),
        ]);

        if (!active) return;

        setProjects(projectRows);
        setTechnicians(technicianRows);
        setSchedules(scheduleRows);
        setManagerEligible(
          managers.some(manager => manager.id === actorId)
        );

        const projectIds = Array.from(new Set(
          scheduleRows.filter(
            row => row.installation_manager === actorId
          ).map(row => row.project)
        ));

        const found: Record<string, Assignment[]> = {};
        const failures: Record<string, string> = {};

        for (const id of projectIds) {
          if (!active) return;

          try {
            found[id] = await readAll<Assignment>(
              'technical-assignment-history/?project=' +
              encodeURIComponent(id)
            );
          } catch (err) {
            failures[id] = (err as Error).message;
          }
        }

        if (active) {
          setAssignments(found);
          setAssignmentErrors(failures);
        }
      } catch (err) {
        if (active) {
          setLoadError((err as Error).message);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => { active = false; };
  }, [api, actorId, revision]);

  const existingProjectIds = new Set(
    schedules.filter(schedule =>
      ['SCHEDULED', 'COMPLETED'].includes(schedule.status)
    ).map(schedule => schedule.project)
  );

  const selectableProjects = projects.filter(project =>
    project.state !== 'CANCELLED' &&
    !existingProjectIds.has(project.id)
  );

  const selectedProject = selectableProjects.find(
    project => project.id === projectId
  );

  const mySchedules = schedules.filter(
    schedule => schedule.installation_manager === actorId
  );

  const upcoming = mySchedules.filter(
    schedule => schedule.status === 'SCHEDULED'
  ).sort((a, b) =>
    a.scheduled_date.localeCompare(b.scheduled_date)
  );

  const history = mySchedules.filter(
    schedule => schedule.status !== 'SCHEDULED'
  ).sort((a, b) =>
    b.scheduled_date.localeCompare(a.scheduled_date)
  );

  function clearAssessment() {
    setAssessment(null);
    setError('');
    setSuccess('');
  }

  function toggleTechnician(id: string) {
    setTechnicianIds(current =>
      current.includes(id)
        ? current.filter(value => value !== id)
        : [...current, id]
    );
    clearAssessment();
  }

  async function save() {
    if (inFlight.current || busy || uncertain) return;

    if (
      loading ||
      loadError ||
      !managerEligible ||
      !selectedProject ||
      !date ||
      technicianIds.length === 0 ||
      technicianIds.length > 25 ||
      !technicianIds.every(id =>
        technicians.some(technician => technician.id === id)
      )
    ) {
      setError(
        'Choose a valid project, installation date and at least one technician.'
      );
      return;
    }

    const requestedProject = projectId;
    const requestedDate = date;
    const requestedTechnicians = [...technicianIds];

    inFlight.current = true;
    setBusy(true);
    setError('');
    setSuccess('');
    setAssessment(null);

    let writeAttempted = false;

    try {
      const result = await api<Assessment>(
        'installation-schedules/assess-proposed-date/',
        'POST',
        {
          project: requestedProject,
          scheduled_date: requestedDate,
        }
      );

      if (
        result.project_id !== requestedProject ||
        result.scheduled_date !== requestedDate ||
        result.installation_authorized ||
        result.installation_started ||
        result.expedited_authorized
      ) {
        throw new Error(
          'The proposed-date assessment could not be verified.'
        );
      }

      setAssessment(result);

      if (
        !result.scheduling_candidate ||
        !result.normal_date_eligible ||
        !result.payment_ready
      ) {
        throw new Error(
          !result.normal_date_eligible
            ? 'The proposed date does not satisfy the verified waiting period.'
            : result.payment_explanation ||
              'Installation requirements remain outstanding.'
        );
      }

      writeAttempted = true;

      const saved = await api<CombinedResult>(
        'schedule-and-assign/',
        'POST',
        {
          project: requestedProject,
          scheduled_date: requestedDate,
          technicians: requestedTechnicians,
        }
      );

      if (
        saved.project_id !== requestedProject ||
        saved.scheduled_date !== requestedDate ||
        saved.installation_manager_id !== actorId ||
        !saved.schedule_id ||
        saved.installation_authorized !== false ||
        saved.installation_started !== false ||
        !Array.isArray(saved.assignments) ||
        saved.assignments.length !== requestedTechnicians.length ||
        !requestedTechnicians.every(id =>
          saved.assignments.some(
            assignment => assignment.technician_id === id
          )
        )
      ) {
        throw new Error('Unexpected combined scheduling response.');
      }

      setSuccess(
        'Schedule and ' + requestedTechnicians.length +
        ' technician assignment(s) saved. ' +
        'The appointment does not authorize installation to start.'
      );

      setProjectId('');
      setDate('');
      setTechnicianIds([]);
      setAssessment(null);
      setRevision(value => value + 1);

    } catch (err) {
      const explanation = (err as Error).message;

      if (writeAttempted) {
        setUncertain(true);
        setError(
          'The combined save was not confirmed. ' +
          'Check the schedule and assignment records before trying again. ' +
          explanation
        );
        setRevision(value => value + 1);
      } else {
        setError(explanation);
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function scheduleRows(records: Schedule[]) {
    if (records.length === 0) {
      return <p className="muted">No records to display.</p>;
    }

    return <div className="unified-schedule-records-5979">
      {records.map(schedule => {
        const project = projects.find(
          item => item.id === schedule.project
        );

        const assigned = (assignments[schedule.project] || [])
          .filter(assignment =>
            assignment.status === 'ACTIVE' &&
            assignment.effective_date <= schedule.scheduled_date
          );

        return <div
          className="unified-schedule-record-5979"
          key={schedule.id}>

          <div>
            <strong>
              {project?.customer_name || 'Project details unavailable'}
            </strong>
            <p>{project?.location}</p>
            <p className="muted">{project?.code || schedule.project}</p>
          </div>

          <div>
            <strong>{displayDate(schedule.scheduled_date)}</strong>
            <p>{schedule.status.replaceAll('_', ' ')}</p>
          </div>

          <div>
            <strong>Assigned technicians</strong>

            {assignmentErrors[schedule.project] ?
              <p role="alert">Assignment records unavailable.</p> :
              assigned.length > 0 ?
                assigned.map(assignment =>
                  <p key={assignment.id}>
                    {technicianName(assignment)}
                  </p>
                ) :
                <p>No active assignment confirmed.</p>}
          </div>
        </div>;
      })}
    </div>;
  }

  return <section className="unified-scheduling-5979">

    <div className="unified-schedule-toolbar-5979">
      <details>
        <summary>Instructions</summary>
        <p>Choose the project, proposed date and technicians.</p>
        <p>
          The server checks the applicable installation requirements
          before saving the schedule and assignments together.
        </p>
        <p>
          Selecting a technician does not establish calendar
          availability. Confirm availability before saving.
        </p>
      </details>

      <button type="button" className="quiet"
        disabled={busy || loading}
        onClick={() => setRevision(value => value + 1)}>
        Refresh
      </button>
    </div>

    {loading && <p role="status">
      Loading authorized projects, technicians and schedules...
    </p>}

    {loadError && <p role="alert" className="error">
      Unable to load scheduling records: {loadError}
    </p>}

    {!loading && !loadError && !managerEligible &&
      <p role="alert" className="error">
        Your installation scheduling authority could not be established.
      </p>}

    <form onSubmit={event => {
      event.preventDefault();
      void save();
    }}>

      <fieldset disabled={
        busy || loading || Boolean(loadError) ||
        !managerEligible || uncertain
      }>

        <h2>Schedule an installation</h2>

        <label>1. Choose project
          <select required value={projectId}
            onChange={event => {
              setProjectId(event.target.value);
              clearAssessment();
            }}>
            <option value="">Choose project</option>
            {selectableProjects.map(project =>
              <option key={project.id} value={project.id}>
                {project.customer_name} - {project.code}
              </option>
            )}
          </select>
        </label>

        {selectedProject &&
          <div className="installation-project-5971">
            <h3>{selectedProject.customer_name}</h3>
            <p>{selectedProject.location}</p>
            <p className="muted">{selectedProject.code}</p>

            <button type="button" className="quiet"
              onClick={() => onReadiness(selectedProject.id)}>
              Check installation readiness
            </button>
          </div>}

        {!loading && selectableProjects.length === 0 &&
          <p>No unscheduled projects are currently available.</p>}

        <label>2. Installation date
          <input type="date" required value={date}
            onChange={event => {
              setDate(event.target.value);
              clearAssessment();
            }}
          />
        </label>

        <div className="unified-technicians-5979">
          <h3>3. Assign technicians</h3>

          {technicians.length === 0 && !loading &&
            <p>No authorized technicians are available for selection.</p>}

          {technicians.map(technician =>
            <label key={technician.id}
              className="unified-technician-option-5979">
              <input type="checkbox"
                checked={technicianIds.includes(technician.id)}
                onChange={() => toggleTechnician(technician.id)}
              />
              <span>{employeeName(technician)}</span>
            </label>
          )}

          <p className="muted">
            {technicianIds.length} technician(s) selected.
            Confirm their availability before saving.
          </p>
        </div>

        <p className="automatic-manager-5973">
          <strong>Responsible Installation Manager:</strong>
          {' '}{actorName}
        </p>

        {assessment && !assessment.scheduling_candidate &&
          <p role="alert" className="error">
            Required scheduling conditions have not been satisfied.
          </p>}

        <button type="submit"
          disabled={
            !selectedProject ||
            !date ||
            technicianIds.length === 0 ||
            technicianIds.length > 25
          }>
          {busy
            ? 'Checking requirements and saving...'
            : 'Save schedule and assignments'}
        </button>

      </fieldset>
    </form>

    {error && <p role="alert" className="error">{error}</p>}

    {success && <p role="status"
      className="installation-assignment-success-5971">
      {success}
    </p>}

    {uncertain &&
      <p role="alert">
        Saving is paused. Review the refreshed schedule and
        assignment records before leaving this screen.
        Do not resubmit an unconfirmed transaction.
      </p>}

    <section className="unified-upcoming-5979">
      <h2>Upcoming installations</h2>

      {loading
        ? <p>Loading installation records...</p>
        : loadError
          ? <p>Installation records are unavailable.</p>
          : scheduleRows(upcoming)}

      <details className="unified-history-5979">
        <summary>Installation history</summary>
        <p className="muted">
          Technician details show currently active assignments,
          not reconstructed historical work records.
        </p>
        {!loading && !loadError && scheduleRows(history)}
      </details>

      <details className="unified-history-5979">
        <summary>Manage existing assignments</summary>
        <p>
          Review, add or end assignments for an existing project.
        </p>
        <button type="button" className="quiet"
          disabled={busy}
          onClick={onExistingAssignments}>
          Open technician assignments
        </button>
      </details>

    </section>

  </section>;
}
