import { useEffect, useRef, useState } from 'react';

type Api = <T,>(
  path: string,
  method?: string,
  data?: unknown
) => Promise<T>;

type Page<T> = {
  results: T[];
  next: string | null;
  count: number;
};

type Project = {
  id: string;
  code: string;
  customer_name: string;
  location: string;
};

type Technician = {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
};

type Assignment = {
  id: string;
  project: string;
  technical_associate: string;
  technician_username: string;
  technician_first_name: string;
  technician_last_name: string;
  assigned_by: string;
  effective_date: string;
  status: 'ACTIVE' | 'ENDED';
  ended_at: string | null;
};

function technicianLabel(assignment: Assignment): string {
  const name = [
    assignment.technician_first_name,
    assignment.technician_last_name,
  ].filter(Boolean).join(' ').trim();

  return name
    ? `${name} (${assignment.technician_username})`
    : assignment.technician_username;
}

export function TechnicianAssignments({ api }: { api: Api }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [techniciansLoading, setTechniciansLoading] = useState(false);
  const [techniciansError, setTechniciansError] = useState('');
  const [projectId, setProjectId] = useState('');
  const [technicianId, setTechnicianId] = useState('');
  const [effectiveDate, setEffectiveDate] = useState('');
  const [assignmentBusy, setAssignmentBusy] = useState(false);
  const assignmentRequestInFlight = useRef(false);
  const [historyRevision, setHistoryRevision] = useState(0);
  const savedAssignmentProjectRef = useRef('');
  const [assignmentConfirmed, setAssignmentConfirmed] = useState(false);
  const [assignmentError, setAssignmentError] = useState('');
  const [assignmentMessage, setAssignmentMessage] = useState('');
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [endingAssignmentId, setEndingAssignmentId] = useState('');
  const [endConfirmed, setEndConfirmed] = useState(false);
  const [endBusy, setEndBusy] = useState(false);
  const [endError, setEndError] = useState('');
  const [endMessage, setEndMessage] = useState('');
  const endRequestInFlight = useRef(false);
  const uncertainEndAssignmentIdsRef = useRef<Set<string>>(new Set());
  const pendingEndVerificationRef = useRef<{
    projectId: string;
    assignmentId: string;
  } | null>(null);

  useEffect(() => {
    let active = true;

    async function loadProjects() {
      setLoading(true);
      setError('');

      try {
        const all: Project[] = [];
        let page = 1;

        while (true) {
          const result = await api<Page<Project>>(
            `operational-projects/?page=${page}`
          );

          all.push(...result.results);

          if (!result.next) break;
          page += 1;
        }

        if (active) setProjects(all);
      } catch (err) {
        if (active) setError((err as Error).message);
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadProjects();

    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    let active = true;

    setHistoryError('');

    if (!projectId) {
      setAssignments([]);
      setHistoryLoading(false);
      return () => { active = false; };
    }

    async function loadHistory() {
      setHistoryLoading(true);
      setEndingAssignmentId('');
      setEndConfirmed(false);
      setEndError('');
      setEndMessage('');

      try {
        const all: Assignment[] = [];
        let page = 1;

        while (true) {
          const result = await api<Page<Assignment>>(
            `technical-assignment-history/?project=${encodeURIComponent(projectId)}&page=${page}`
          );

          all.push(...result.results);

          if (!result.next) break;
          page += 1;
        }

        if (active) {
          setAssignments(all);
          setHistoryError('');
          const pendingEnd = pendingEndVerificationRef.current;
          if (pendingEnd?.projectId === projectId) {
            const verified = all.some(assignment =>
              assignment.id === pendingEnd.assignmentId &&
              assignment.project === projectId &&
              assignment.status === 'ENDED' &&
              Boolean(assignment.ended_at)
            );
            setEndMessage(
              verified
                ? 'Technician assignment ended. Its status and end time are confirmed in assignment history.'
                : 'The termination response was received, but the updated history could not confirm the result. Do not try again. Ask an authorized manager to check the assignment.'
            );
            pendingEndVerificationRef.current = null;
          }
          if (savedAssignmentProjectRef.current === projectId) {
            setAssignmentMessage(
              'Technician assignment saved. Assignment history is up to date.'
            );
            savedAssignmentProjectRef.current = '';
          }
        }
      } catch (err) {
        if (active) {
          const message = err instanceof Error
            ? err.message
            : 'An unexpected error occurred.';
          setHistoryError(message);
          if (pendingEndVerificationRef.current?.projectId === projectId) {
            setEndMessage(
              'The termination response was received, but assignment history could not be checked. Do not try again. Ask an authorized manager to verify the result.'
            );
            pendingEndVerificationRef.current = null;
          }
          if (savedAssignmentProjectRef.current === projectId) {
            setAssignmentMessage(
              'Technician assignment was saved, but its history could not be refreshed. ' +
              'Do not create another assignment. Ask an authorized manager to check the history.'
            );
            savedAssignmentProjectRef.current = '';
          }
        }
      } finally {
        if (active) setHistoryLoading(false);
      }
    }

    void loadHistory();

    return () => { active = false; };
  }, [api, projectId, historyRevision]);

  useEffect(() => {
    let active = true;

    async function loadTechnicians() {
      setTechniciansLoading(true);
      setTechniciansError('');

      try {
        const result = await api<Technician[]>(
          'technicians/'
        );

        if (active) setTechnicians(result);
      } catch (err) {
        if (active) setTechniciansError((err as Error).message);
      } finally {
        if (active) setTechniciansLoading(false);
      }
    }

    void loadTechnicians();

    return () => { active = false; };
  }, [api]);

  async function createAssignment() {
    if (assignmentRequestInFlight.current || assignmentBusy) return;

    const validProject = projects.some(project => project.id === projectId);
    const validTechnician = technicians.some(
      technician => technician.id === technicianId
    );

    if (
      !assignmentConfirmed ||
      !validProject ||
      !validTechnician ||
      !effectiveDate ||
      techniciansLoading ||
      historyLoading
    ) {
      setAssignmentError(
        'Choose a project, Technician, and effective date. ' +
        'Review the details and check the confirmation box.'
      );
      return;
    }

    assignmentRequestInFlight.current = true;
    setAssignmentBusy(true);
    setAssignmentError('');
    setAssignmentMessage('');

    try {
      await api<Assignment>('technical-assignments/', 'POST', {
        project: projectId,
        technical_associate: technicianId,
        effective_date: effectiveDate
      });

      setAssignmentConfirmed(false);
      setTechnicianId('');
      setEffectiveDate('');
      setAssignmentMessage(
        'Technician assignment saved. Checking the updated history.'
      );
      savedAssignmentProjectRef.current = projectId;
      setHistoryRevision(revision => revision + 1);
    } catch (err) {
      const message = err instanceof Error
        ? err.message
        : 'An unexpected error occurred.';

      const duplicateNotice =
        'This Technician already has an active assignment to this project. ' +
        'Review the active assignments below. ' +
        'You do not need to create another assignment.';

      const uncertainResponse =
        message.includes('The server returned an unexpected response.');

      setAssignmentError(
        message.includes(duplicateNotice)
          ? duplicateNotice
          : uncertainResponse
            ? 'The server response was unclear. The assignment may have been saved. ' +
              'Check the assignment history before trying again. ' +
              'If you cannot confirm the result, ask an authorized manager to check.'
            : `Assignment was not created. ${message}`
      );
      setAssignmentConfirmed(false);
    } finally {
      assignmentRequestInFlight.current = false;
      setAssignmentBusy(false);
    }
  }

  async function endAssignment() {
    if (endRequestInFlight.current || endBusy) return;

    if (pendingEndVerificationRef.current !== null) {
      setEndError(
        'A previous termination is still being checked. ' +
        'Do not send another request until the assignment history is verified.'
      );
      return;
    }

    if (uncertainEndAssignmentIdsRef.current.has(endingAssignmentId)) {
      setEndError(
        'The result of an earlier termination request is unclear. ' +
        'Do not submit it again. Ask an authorized manager to verify the record.'
      );
      return;
    }

    const selected = assignments.find(assignment =>
      assignment.id === endingAssignmentId &&
      assignment.project === projectId &&
      assignment.status === 'ACTIVE'
    );

    if (
      !endConfirmed ||
      !selected ||
      !projects.some(project => project.id === projectId) ||
      historyLoading ||
      Boolean(historyError) ||
      assignmentBusy
    ) {
      setEndError(
        'Choose an active assignment. Review the Technician and project, ' +
        'then check the confirmation box.'
      );
      return;
    }

    const assignmentId = selected.id;
    const selectedProjectId = projectId;

    endRequestInFlight.current = true;
    setEndBusy(true);
    setEndError('');
    setEndMessage('');
    setEndConfirmed(false);

    try {
      const result = await api<Assignment>(
        `technical-assignments/${encodeURIComponent(assignmentId)}/end/`,
        'POST'
      );

      pendingEndVerificationRef.current = {
        projectId: selectedProjectId,
        assignmentId,
      };

      if (
        result?.id !== assignmentId ||
        result?.project !== selectedProjectId ||
        result?.status !== 'ENDED' ||
        !result?.ended_at
      ) {
        uncertainEndAssignmentIdsRef.current.add(assignmentId);
        setEndMessage(
          'The server returned an unexpected termination result. ' +
          'Checking assignment history before confirming the change.'
        );
      } else {
        setEndMessage(
          'The server accepted the termination. ' +
          'Checking assignment history before confirming the change.'
        );
      }

      setHistoryRevision(revision => revision + 1);
    } catch (err) {
      uncertainEndAssignmentIdsRef.current.add(assignmentId);

      const message = err instanceof Error
        ? err.message
        : 'An unexpected error occurred.';

      setEndError(
        'The assignment could not be confirmed as ended. ' +
        'The server may have processed the request. ' +
        'Do not send another termination request. ' +
        'Ask an authorized manager to verify the assignment history. ' +
        `Server message: ${message}`
      );
    } finally {
      endRequestInFlight.current = false;
      setEndBusy(false);
    }
  }
  const activeAssignments = assignments.filter(
    assignment => assignment.status === 'ACTIVE'
  );

  const endedAssignments = assignments.filter(
    assignment => assignment.status === 'ENDED'
  );

  function renderAssignments(items: Assignment[], emptyMessage: string) {
    if (items.length === 0) {
      return <p className="muted">{emptyMessage}</p>;
    }

    return <ul>
      {items.map(assignment => <li key={assignment.id}>
        <strong>{technicianLabel(assignment)}</strong>
        <p>Effective date: {assignment.effective_date}</p>
        <p>Status: {assignment.status === 'ACTIVE' ? 'Active' : 'Ended'}</p>
        {assignment.ended_at && <p>
          Ended: {new Date(assignment.ended_at).toLocaleString()}
        </p>}
      </li>)}
    </ul>;
  }

  return <section>
    <div className="veridian-guide-banner veridian-guide-banner--info">
      <strong>Step 1 — Choose a project</strong>
      <p>
        Select a project to see its Technician assignments.
        Review the active and previous assignments before making changes.
        Choosing a project does not save anything.
      </p>
    </div>


    <p className="muted">
      This screen shows assignment responsibility only.
      It does not approve compensation or payments.
    </p>

    {error && <p role="alert" className="error">{error}</p>}

    <label htmlFor="technician-assignment-project">
      Project
    </label>
    <select
      id="technician-assignment-project"
      value={projectId}
      disabled={loading || assignmentBusy || endBusy}
      onChange={event => {
        setProjectId(event.target.value);
        setEndingAssignmentId('');
        setEndConfirmed(false);
        setEndError('');
        setEndMessage('');
        setTechnicianId('');
        setEffectiveDate('');
        setAssignmentConfirmed(false);
        setAssignmentError('');
        setAssignmentMessage('');
        savedAssignmentProjectRef.current = '';
        setAssignments([]);
      }}
    >
      <option value="">Choose project</option>
      {projects.map(project => <option
        key={project.id}
        value={project.id}
      >
        {project.code} - {project.customer_name}
      </option>)}
    </select>

    {loading && <p role="status">Loading authorized projects...</p>}

    {!loading && projects.length === 0 && !error &&
      <p role="status">No authorized projects are available.</p>}

    {projectId && <>
      {assignmentError &&
        <p role="alert" className="error">{assignmentError}</p>}

      {assignmentMessage &&
        <p role="status">{assignmentMessage}</p>}

      <h3>Choose a Technician</h3>
      <p className="muted">
        Select an active Technician for this project.
        This step does not create an assignment.
      </p>

      {techniciansLoading &&
        <p role="status">Loading available Technicians...</p>}

      {techniciansError &&
        <p role="alert" className="error">{techniciansError}</p>}

      {!techniciansLoading && !techniciansError &&
        technicians.length === 0 &&
        <p role="status">
          No active Technicians are available.
          Ask an authorized Administrator to add or activate
          a Technician account before making an assignment.
        </p>}

      <label htmlFor="technician-assignment-technician">
        Technician
      </label>
      <select
        id="technician-assignment-technician"
        value={technicianId}
        disabled={
          assignmentBusy ||
          techniciansLoading ||
          Boolean(techniciansError) ||
          technicians.length === 0
        }
        onChange={event => {
          setTechnicianId(event.target.value);
          setAssignmentConfirmed(false);
        }}
      >
        <option value="">Choose Technician</option>
        {technicians.map(technician => <option
          key={technician.id}
          value={technician.id}
        >
          {[
            technician.first_name,
            technician.last_name
          ].filter(Boolean).join(' ').trim() || technician.username}
          {' ('}{technician.username}{')'}
        </option>)}
      </select>

      <label htmlFor="technician-assignment-effective-date">
        Assignment effective date
      </label>
      <input
        id="technician-assignment-effective-date"
        type="date"
        value={effectiveDate}
        required
        disabled={
          assignmentBusy ||
          techniciansLoading ||
          Boolean(techniciansError) ||
          technicians.length === 0
        }
        onChange={event => {
          setEffectiveDate(event.target.value);
          setAssignmentConfirmed(false);
        }}
      />

      <p className="muted">
        Choose the date when the Technician's assignment begins.
        Selecting a date does not create an assignment.
      </p>

      {projectId && technicianId && effectiveDate &&
        projects.some(project => project.id === projectId) &&
        technicians.some(technician => technician.id === technicianId) &&
        <div className="documents">
          <h3>Review proposed assignment</h3>
          <p>
            <strong>Project:</strong>{' '}
            {projects.find(project => project.id === projectId)?.code}
            {' - '}
            {projects.find(project => project.id === projectId)?.customer_name}
          </p>
          <p>
            <strong>Technician:</strong>{' '}
            {[
              technicians.find(technician => technician.id === technicianId)?.first_name,
              technicians.find(technician => technician.id === technicianId)?.last_name
            ].filter(Boolean).join(' ').trim() ||
              technicians.find(technician => technician.id === technicianId)?.username}
          </p>
          <p>
            <strong>Effective date:</strong> {effectiveDate}
          </p>
          <p className="muted">
            Review these details carefully before creating an assignment.
            This review does not save any changes.
          </p>
          <label className="sandbox-confirm">
            <input
              type="checkbox"
              checked={assignmentConfirmed}
              disabled={assignmentBusy}
              onChange={event => setAssignmentConfirmed(event.target.checked)}
            />
            <span>I checked the project, Technician, and effective date.</span>
          </label>
        </div>}

      <p className="muted">
        Selecting a Technician does not save an assignment.
        Review and confirm the details before creating one.
      </p>

      <button
        type="button"
        disabled={
          assignmentBusy ||
          historyLoading ||
          techniciansLoading ||
          Boolean(techniciansError) ||
          !assignmentConfirmed ||
          !projectId ||
          !technicianId ||
          !effectiveDate ||
          !projects.some(project => project.id === projectId) ||
          !technicians.some(technician => technician.id === technicianId)
        }
        onClick={() => { void createAssignment(); }}
      >
        {assignmentBusy
          ? 'Creating assignment...'
          : 'Create Technician Assignment'}
      </button>

      {assignmentBusy &&
        <p role="status">Saving the Technician assignment...</p>}

      <div className="veridian-guide-banner veridian-guide-banner--info">
        <strong>Step 2 — Review assignments</strong>
        <p>
          Check who is currently assigned to this project.
          Review previous assignments too.
          Nothing changes until you confirm an action.
        </p>
      </div>
      <h3>Assignment history</h3>

      {historyLoading &&
        <p role="status">Loading Technician assignment history...</p>}

      {historyError &&
        <p role="alert" className="error">{historyError}</p>}

      {!historyLoading && !historyError && <>
        <h4>Active assignments ({activeAssignments.length})</h4>
        {renderAssignments(activeAssignments, "No active Technician assignments for this project.")}

        <h4>Previous assignments ({endedAssignments.length})</h4>
        {renderAssignments(endedAssignments, "No previous Technician assignments for this project.")}
      </>}
      <div className="documents">
        <h3>End a Technician Assignment</h3>

        {endError &&
          <p role="alert" className="error">{endError}</p>}

        {endMessage &&
          <p role="status">{endMessage}</p>}

        {endBusy &&
          <p role="status">
            Processing the termination request. Do not submit it again.
          </p>}

        <div className="veridian-guide-banner veridian-guide-banner--info">
          <strong>Step 3 — Choose an active assignment</strong>
          <p>
            Choose the Technician assignment you want to end.
            Selecting an assignment does not change its status.
          </p>
        </div>

        <label htmlFor="technician-end-assignment-select">
          Active assignment to review
        </label>
        <select
          id="technician-end-assignment-select"
          value={endingAssignmentId}
          disabled={historyLoading || Boolean(historyError) || assignmentBusy || endBusy}
          onChange={event => {
            setEndingAssignmentId(event.target.value);
            setEndConfirmed(false);
            setEndError('');
            setEndMessage('');
          }}
        >
          <option value="">Choose an active assignment</option>
          {activeAssignments.map(assignment =>
            <option key={assignment.id} value={assignment.id}>
              {technicianLabel(assignment)} — {assignment.effective_date}
            </option>
          )}
        </select>

        {activeAssignments.length === 0 && !historyLoading && !historyError &&
          <p className="muted">
            There are no active Technician assignments to end for this project.
          </p>}

        {activeAssignments.filter(assignment =>
          assignment.id === endingAssignmentId
        ).map(assignment => <div key={assignment.id} className="documents">
          <h3>Review the selected assignment</h3>
          <p><strong>Technician:</strong> {technicianLabel(assignment)}</p>
          <p><strong>Project:</strong> {
            projects.find(project => project.id === assignment.project)?.code
          }</p>
          <p><strong>Assignment start date:</strong> {assignment.effective_date}</p>
          <div className="veridian-guide-banner veridian-guide-banner--caution">
            <strong>Step 4 — Check before ending</strong>
            <p>
              Ending this assignment removes it from the active list.
              Its record will remain in Previous assignments.
              Nothing has been changed yet.
            </p>
          </div>
          <label className="sandbox-confirm">
            <input
              type="checkbox"
              checked={endConfirmed}
              disabled={endBusy || historyLoading || Boolean(historyError)}
              onChange={event => {
                setEndConfirmed(event.target.checked);
                setEndError('');
              }}
            />
            I checked the Technician and project. I understand that ending
            this assignment will remove it from the active list.
          </label>
          <button
            type="button"
            disabled={
              !endConfirmed ||
              endBusy ||
              assignmentBusy ||
              historyLoading ||
              Boolean(historyError) ||
              pendingEndVerificationRef.current !== null ||
              uncertainEndAssignmentIdsRef.current.has(assignment.id) ||
              assignment.project !== projectId ||
              assignment.status !== 'ACTIVE'
            }
            onClick={() => { void endAssignment(); }}
          >
            {endBusy ? 'Ending assignment...' : 'End Technician Assignment'}
          </button>
        </div>)}
      </div>
    </>}
  </section>;
}