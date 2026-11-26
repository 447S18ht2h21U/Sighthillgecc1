import { useEffect, useState } from 'react';

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

type Schedule = {
  id: string;
  project: string;
  scheduled_date: string;
  installation_manager: string;
  installation_manager_display: string;
  status: string;
};

type Requirements = {
  approved_msr: boolean;
  contract_signed: boolean;
  cancellation_complete: boolean;
  waiting_period_complete: boolean;
  deposit_verified: boolean;
};

type InstallationDateRequirements = {
  status: 'NOT_ESTABLISHED' | 'PROVISIONAL' | 'ESTABLISHED';
  contract_signed_at: string | null;
  transaction_date: string | null;
  required_business_days: number | null;
  effective_cancellation_deadline: string | null;
  earliest_normal_installation_date: string | null;
  blocking_reasons: string[];
  installation_authorized: boolean;
  expedited_authorized: boolean;
};

type Assessment = {
  installation_date_requirements?: InstallationDateRequirements;
  project_id: string;
  eligible: boolean;
  requirements: Requirements;
  blocking_reasons: string[];
  installation_start?: {
    installation_authorized: boolean;
    installation_started: boolean;
    blockers: string[];
  };
};

type WorkItem = {
  project: Project;
  assessment: Assessment | null;
  error?: string;
};

type Queue = 'all' | 'ready' | 'blocked' | 'unavailable';

const requirements: {
  key: keyof Requirements;
  title: string;
  owner: string;
  action: string;
}[] = [
  {
    key: 'approved_msr',
    title: 'Sales record approval',
    owner: 'Sales Manager; Comptroller or CEO',
    action:
      'Complete the sales review and obtain the required independent approval.',
  },
  {
    key: 'contract_signed',
    title: 'Verified customer Contract signature',
    owner: 'Sales Manager; Comptroller or CEO',
    action:
      'Obtain the required signatures and confirm the signed documents.',
  },
  {
    key: 'cancellation_complete',
    title: 'Customer cancellation period',
    owner: 'Comptroller or CEO',
    action:
      'Verify the applicable cancellation deadline and confirm it has passed.',
  },
  {
    key: 'waiting_period_complete',
    title: 'Installation waiting period',
    owner: 'Installation Manager',
    action:
      'Choose a proposed date that satisfies the applicable waiting period.',
  },
  {
    key: 'deposit_verified',
    title: 'Required customer payment',
    owner: 'Installation Manager; Comptroller or CEO',
    action:
      'Collect the required payment and obtain independent bank verification, or confirm an applicable approved payment exception.',
  },
];

async function readAll<T extends { id: string }>(
  api: Api,
  path: string,
): Promise<T[]> {
  const found = new Map<string, T>();

  for (let page = 1; page <= 100; page++) {
    const batch = await api<Page<T>>(
      path + '?page=' + page
    );

    if (!Array.isArray(batch.results)) {
      throw new Error('Invalid server record list.');
    }

    for (const row of batch.results) {
      if (!row || typeof row.id !== 'string' || !row.id) {
        throw new Error('A server record is missing its identifier.');
      }

      const previous = found.get(row.id);

      if (
        previous &&
        JSON.stringify(previous) !== JSON.stringify(row)
      ) {
        throw new Error('Conflicting server records were received.');
      }

      found.set(row.id, row);
    }

    if (!batch.next) return Array.from(found.values());
  }

  throw new Error('The record list exceeds the current review limit.');
}

function validateAssessment(
  projectId: string,
  result: Assessment,
) {
  if (
    !result ||
    result.project_id !== projectId ||
    typeof result.eligible !== 'boolean' ||
    !result.requirements ||
    !Array.isArray(result.blocking_reasons) ||
    !result.blocking_reasons.every(reason =>
      typeof reason === 'string'
    ) ||
    !requirements.every(item =>
      typeof result.requirements[item.key] === 'boolean'
    )
  ) {
    throw new Error('The readiness assessment could not be verified.');
  }

  if (
    result.eligible &&
    (
      !requirements.every(item =>
        result.requirements[item.key]
      ) ||
      result.blocking_reasons.length > 0
    )
  ) {
    throw new Error('The readiness assessment contains conflicting results.');
  }

  return result;
}

function formatInstallationDate5988(value: string | null | undefined) {
  if (!value || !/^\\d{4}-\\d{2}-\\d{2}$/.test(value)) {
    return 'Not yet established';
  }

  const parsed = new Date(value + 'T12:00:00Z');

  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.toISOString().slice(0,10)!==value
  ) {
    return 'Not yet established';
  }

  return parsed.toLocaleDateString('en-US',{
    weekday:'long',
    month:'long',
    day:'numeric',
    year:'numeric',
    timeZone:'UTC',
  });
}

function formatEvidenceTime5988(value: string | null | undefined) {
  if (
    !value ||
    !/(Z|[+-]\\d{2}:\\d{2})$/.test(value)
  ) {
    return 'Awaiting verification';
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return 'Awaiting verification';
  }

  return parsed.toLocaleString('en-US',{
    timeZone:'America/New_York',
    dateStyle:'medium',
    timeStyle:'short',
  }) + ' ET';
}

function InstallationDateRequirements5988({
  assessment,
}: {
  assessment: Assessment;
}) {
  const dates = assessment.installation_date_requirements;

  const established = Boolean(
    dates?.status==='ESTABLISHED' &&
    dates.earliest_normal_installation_date &&
    dates.effective_cancellation_deadline
  );

  const earliest = established
    ? formatInstallationDate5988(
        dates?.earliest_normal_installation_date
      )
    : 'Not yet established';

  return <section className="installation-date-requirements-5988">

    <h3>Installation date requirements</h3>

    <dl className="installation-date-facts-5988">

      <dt>Customer Contract signed</dt>
      <dd>{
        assessment.requirements.contract_signed
          ? formatEvidenceTime5988(dates?.contract_signed_at)
          : 'Awaiting verification'
      }</dd>

      <dt>Customer cancellation period</dt>
      <dd>{
        dates?.required_business_days===5
          ? '5 business days'
          : dates?.required_business_days===7
            ? '7 business days'
            : 'Awaiting verification'
      }</dd>

      <dt>Customer cancellation deadline</dt>
      <dd>{
        established
          ? formatEvidenceTime5988(
              dates?.effective_cancellation_deadline
            )
          : 'Not yet established'
      }</dd>

    </dl>

    <div className="earliest-installation-date-5988">
      <span>Earliest normal installation date</span>
      <strong>{earliest}</strong>
    </div>

    {!established&&
      <p>
        Complete the required customer and Contract verification.
        VERIDIAN will calculate the installation date.
      </p>}

    <div className="installation-date-options-5988">

      <div>
        <strong>Normal installation</strong>
        <p>
          Schedule installation on or after the earliest
          permitted installation date.
        </p>
      </div>

      <div>
        <strong>Expedited installation</strong>
        <p>
          Obtain a customer-signed Request for Expedited Service
          and Installation Manager approval.
          Applicable legal requirements must be satisfied.
        </p>
        <p className="muted">
          A signed request alone does not remove the
          customer's legal cancellation rights.
        </p>
      </div>

    </div>

    <p className="muted">
      Responsible: Installation Manager.
      Coordinate outstanding Contract and cancellation
      verification with the Comptroller or CEO.
    </p>

    {dates?.blocking_reasons?.length
      ? <details>
          <summary>View outstanding date requirements</summary>
          <ul>
            {dates.blocking_reasons.map((reason,index)=>
              <li key={index}>{reason}</li>
            )}
          </ul>
        </details>
      : null}

  </section>;
}

export function InstallationReadinessWorklist5981({
  api,
  initialProjectId = '',
  onSchedule,
}: {
  api: Api;
  initialProjectId?: string;
  onSchedule: (projectId: string) => void;
}) {
  const [items, setItems] = useState<WorkItem[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [queue, setQueue] = useState<Queue>('all');
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [checkedAt, setCheckedAt] = useState('');

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError('');
    setItems([]);
    setProjects([]);
    setSchedules([]);
    setCheckedAt('');
    setProgress('Loading authorized projects...');

    void (async () => {
      try {
        const [projectRows, scheduleRows] = await Promise.all([
          readAll<Project>(api, 'operational-projects/'),
          readAll<Schedule>(api, 'installation-schedules/'),
        ]);

        if (!active) return;

        setProjects(projectRows);
        setSchedules(scheduleRows);

        const existing = new Set(
          scheduleRows
            .filter(schedule =>
              ['SCHEDULED', 'COMPLETED'].includes(schedule.status)
            )
            .map(schedule => schedule.project)
        );

        const candidates = projectRows.filter(project =>
          project.state !== 'CANCELLED' &&
          !existing.has(project.id)
        );

        const assessed: WorkItem[] = [];

        // Keep the number of simultaneous server requests bounded.
        // No partial response is represented as a complete work list.

        for (let offset = 0; offset < candidates.length; offset += 4) {
          if (!active) return;

          setProgress(
            'Checking projects ' + (offset + 1) +
            ' to ' + Math.min(offset + 4, candidates.length) +
            ' of ' + candidates.length + '...'
          );

          const batch = await Promise.all(
            candidates.slice(offset, offset + 4).map(
              async (project): Promise<WorkItem> => {
                try {
                  const result = await api<Assessment>(
                    'operational-projects/' +
                    encodeURIComponent(project.id) +
                    '/installation-eligibility/'
                  );

                  return {
                    project,
                    assessment: validateAssessment(
                      project.id, result
                    ),
                  };
                } catch (err) {
                  return {
                    project,
                    assessment: null,
                    error: (err as Error).message,
                  };
                }
              }
            )
          );

          assessed.push(...batch);
        }

        if (!active) return;

        setItems(assessed);
        setCheckedAt(new Date().toISOString());

      } catch (err) {
        if (active) setError((err as Error).message);
      } finally {
        if (active) {
          setLoading(false);
          setProgress('');
        }
      }
    })();

    return () => { active = false; };
  }, [api, revision]);

  const ready = items.filter(item =>
    item.assessment?.eligible === true
  );

  const blocked = items.filter(item =>
    item.assessment?.eligible === false
  );

  const unavailable = items.filter(item =>
    item.assessment === null
  );

  const visible = (
    queue === 'ready' ? ready :
    queue === 'blocked' ? blocked :
    queue === 'unavailable' ? unavailable :
    [...blocked, ...unavailable, ...ready]
  ).slice().sort((a, b) => {
    if (a.project.id === initialProjectId) return -1;
    if (b.project.id === initialProjectId) return 1;
    return 0;
  });

  const existingSchedules = schedules.filter(schedule =>
    ['SCHEDULED', 'COMPLETED'].includes(schedule.status)
  ).sort((a, b) =>
    a.scheduled_date.localeCompare(b.scheduled_date)
  );

  function projectCard(item: WorkItem) {
    const { project, assessment } = item;

    return <article
      className="readiness-work-item-5981"
      key={project.id}>

      <div className="readiness-item-heading-5981">
        <div>
          <h3>{project.customer_name}</h3>
          <p>{project.location}</p>
          <p className="muted">{project.code}</p>
        </div>

        <strong className={
          assessment?.eligible
            ? 'readiness-ready-5981'
            : 'readiness-outstanding-5981'
        }>
          {assessment?.eligible === true
            ? 'Ready to schedule'
            : assessment?.eligible === false
              ? 'Requirements outstanding'
              : 'Verification unavailable'}
        </strong>
      </div>

      {!assessment ?
        <>
          <p role="alert">
            The current requirements could not be checked.
            Do not assume this project is ready.
          </p>
          <details>
            <summary>View verification issue</summary>
            <p>{item.error}</p>
          </details>
        </> :
        assessment.eligible ?
          <>
            <p>
              Current scheduling requirements are satisfied.
              Select a proposed installation date.
            </p>

            <InstallationDateRequirements5988
              assessment={assessment}
            />

            <button type="button"
              onClick={() => onSchedule(project.id)}>
              Schedule and assign work
            </button>
          </> :
          <>
            <div className="readiness-actions-5981">

              {requirements.filter(requirement =>
                !assessment.requirements[requirement.key] &&
                ![
                  'cancellation_complete',
                  'waiting_period_complete',
                ].includes(requirement.key)
              ).map(requirement =>
                <div
                  className="readiness-action-5981"
                  key={requirement.key}>

                  <strong>{requirement.title}</strong>
                  <p>{requirement.action}</p>
                  <p className="muted">
                    Responsible: {requirement.owner}
                  </p>
                </div>
              )}

              <InstallationDateRequirements5988
                assessment={assessment}
              />

              {requirements.every(requirement =>
                assessment.requirements[requirement.key]
              ) &&
                <div className="readiness-action-5981">
                  <strong>Additional requirements outstanding</strong>
                  <p>
                    Review the server's outstanding requirements
                    before scheduling.
                  </p>
                </div>}
            </div>

            {assessment.blocking_reasons.length > 0 &&
              <details>
                <summary>View outstanding server requirements</summary>
                <ul>
                  {assessment.blocking_reasons.map(
                    (reason, index) =>
                      <li key={index}>{reason}</li>
                  )}
                </ul>
              </details>}

            <p className="muted">
              VERIDIAN checks the proposed installation date.
              Scheduling does not authorize installation to begin.
            </p>

            <button type="button" className="quiet"
              onClick={() => onSchedule(project.id)}>
              Review scheduling options
            </button>
          </>}

      <details className="readiness-start-details-5981">
        <summary>Authorization to begin installation</summary>

        {assessment?.installation_start?.installation_authorized === true
          ? <p>
              The server reports installation authorization.
              Confirm the current schedule and required work records.
            </p>
          : <p>Installation start is not authorized by this assessment.</p>}

        {assessment?.installation_start?.blockers?.map(
          (reason, index) => <p key={index}>{reason}</p>
        )}

        <p className="muted">
          Readiness to schedule is not permission to begin installation.
        </p>
      </details>

    </article>;
  }

  return <section className="installation-readiness-worklist-5981">

    <div className="readiness-toolbar-5981">
      <div>
        <h2>Projects awaiting installation</h2>
        <p>Review the projects that need your attention.</p>
      </div>

      <button type="button" className="quiet"
        disabled={loading}
        onClick={() => setRevision(value => value + 1)}>
        Refresh
      </button>
    </div>

    <details className="readiness-instructions-5981">
      <summary>Instructions</summary>
      <p>
        VERIDIAN checks authorized projects against the current
        scheduling requirements.
      </p>
      <p>
        Review outstanding requirements and coordinate their resolution
        with the responsible employee.
      </p>
      <p>
        Projects may qualify for a future installation date even
        when today's waiting-period requirements are outstanding.
        Scheduling and installation-start authorization remain separate.
      </p>
    </details>

    {loading &&
      <p role="status">{progress}</p>}

    {error &&
      <p className="error" role="alert">
        Unable to load the complete installation work list.
        {error}
      </p>}

    {!loading && !error && <>

      <div className="readiness-summary-grid-5981">

        <button type="button"
          aria-pressed={queue === 'ready'}
          className={
            'readiness-summary-card-5981 readiness-summary-ready-5981' +
            (queue === 'ready' ? ' selected' : '')
          }
          onClick={() => setQueue(
            queue === 'ready' ? 'all' : 'ready'
          )}>
          <strong>{ready.length}</strong>
          <span>Ready to schedule</span>
          <small>Current requirements satisfied</small>
        </button>

        <button type="button"
          aria-pressed={queue === 'blocked'}
          className={
            'readiness-summary-card-5981 readiness-summary-blocked-5981' +
            (queue === 'blocked' ? ' selected' : '')
          }
          onClick={() => setQueue(
            queue === 'blocked' ? 'all' : 'blocked'
          )}>
          <strong>{blocked.length}</strong>
          <span>Requirements outstanding</span>
          <small>Projects requiring attention</small>
        </button>

      </div>

      {unavailable.length > 0 &&
        <div className="readiness-unavailable-5981">
          <p role="alert">
            Readiness could not be verified for
            {' '}{unavailable.length} project(s).
          </p>
          <button type="button" className="quiet"
            onClick={() => setQueue(
              queue === 'unavailable' ? 'all' : 'unavailable'
            )}>
            {queue === 'unavailable'
              ? 'Show all projects'
              : 'Review unverified projects'}
          </button>
        </div>}

      <div className="readiness-list-heading-5981">
        <h2>{
          queue === 'ready' ? 'Ready to schedule' :
          queue === 'blocked' ? 'Requirements outstanding' :
          queue === 'unavailable' ? 'Readiness unavailable' :
          'Projects requiring attention'
        }</h2>

        {queue !== 'all' &&
          <button type="button" className="quiet"
            onClick={() => setQueue('all')}>
            Show all projects
          </button>}
      </div>

      {checkedAt &&
        <p className="muted">
          Last checked: {
            new Date(checkedAt).toLocaleString('en-US', {
              timeZone: 'America/New_York',
              dateStyle: 'medium',
              timeStyle: 'short',
            })
          } ET
        </p>}

      {visible.length === 0 ?
        <p>No projects in this category.</p> :
        visible.map(projectCard)}

      <details className="readiness-scheduled-history-5981">
        <summary>
          Previously scheduled installations
          {' '}({existingSchedules.length})
        </summary>

        {existingSchedules.length === 0 ?
          <p>No scheduled or completed installations are visible.</p> :
          existingSchedules.map(schedule => {
            const project = projects.find(
              item => item.id === schedule.project
            );

            return <div
              className="readiness-history-row-5981"
              key={schedule.id}>

              <div>
                <strong>
                  {project?.customer_name || 'Project details unavailable'}
                </strong>
                <p>{project?.location}</p>
                <p className="muted">
                  {project?.code || schedule.project}
                </p>
              </div>

              <div>
                <strong>{schedule.scheduled_date}</strong>
                <p>{schedule.status.replaceAll('_', ' ')}</p>
                <p>{schedule.installation_manager_display}</p>
              </div>

            </div>;
          })}

      </details>

    </>}

  </section>;
}
