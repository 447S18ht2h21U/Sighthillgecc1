import { useEffect, useRef, useState } from 'react';
import { CompletionCertificatePreview6049 } from './CompletionCertificatePreview6049';
import { DistributorInvoiceWorkspace6007 } from './DistributorInvoiceWorkspace6007';

type Api = <T,>(
  path:string,
  method?:string,
  data?:unknown
)=>Promise<T>;

type PurchaseSource = {
  serial_number:string;
  invoice_id:string;
  allocation_id:string;
  invoice_number:string;
};

type PhysicalUnit = {
  unit_id:string;
  model_number:string;
  category_of_work:string;
  purchase_required:boolean;
  purchase_serial_number:string|null;
  serial_candidates:PurchaseSource[];
  status:string;
};

type EquipmentConfirmation = {
  unit_id:string;
  serial_number:string;
  confirmed:boolean;
};

type SavedEquipment = EquipmentConfirmation & {
  model_number:string;
  purchase_required:boolean;
  purchase_source:PurchaseSource|null;
};

type Findings = {
  equipment_and_serial_numbers_confirmed:boolean;
  required_materials_confirmed:boolean;
  distributor_invoice_uploaded_and_verified:boolean;
  personally_inspected:boolean;
  scope_completed_professionally:boolean;
  technician_delivered_quality_service:boolean;
  job_site_clean:boolean;
  customer_impression:'SATISFIED'|'UNSATISFIED'|'';
  inspection_notes:string;
  decision:'ACCEPT'|'CORRECTIONS_REQUIRED';
};

type SavedInspection = {
  inspection_id:string;
  status:string;
  recorded_at:string;
  equipment:SavedEquipment[];
  findings:Findings;
  fictional_acceptance_test:boolean;
};

type Workspace = {
  project_id:string;
  project_code:string;
  customer_name:string;
  installation_address:string;
  msr_id:string;
  msr_version:number;
  snapshot_sha256:string;
  manifest_sha256:string;

  equipment_manifest:{
    available:boolean;
    units:PhysicalUnit[];
    required_unit_count:number;
    purchase_serial_unit_count:number;
    distributor_purchase_review_complete:boolean;
    warnings:string[];
  };

  invoice_summary:{
    invoice_id:string;
    allocation_id:string;
    distributor_name:string;
    invoice_number:string;
    invoice_date:string;
    verification_status:string;
    equipment_review_recorded:boolean;
  }[];

  saved_inspection:SavedInspection|null;
  fictional_acceptance_test_required:boolean;
  can_record_inspection:boolean;
  can_send_certificate:boolean;
};

const QUALITY_QUESTIONS = [
  [
    'personally_inspected',
    'I personally inspected the installation.',
  ],
  [
    'scope_completed_professionally',
    'The Project Scope of Work was completed in a professional manner.',
  ],
  [
    'technician_delivered_quality_service',
    'The Technician delivered quality service.',
  ],
  [
    'job_site_clean',
    'The Technician removed debris, leaving a clean job site.',
  ],
] as const;

type QualityKey = typeof QUALITY_QUESTIONS[number][0];

const EMPTY_QUALITY:Record<QualityKey,boolean> = {
  personally_inspected:false,
  scope_completed_professionally:false,
  technician_delivered_quality_service:false,
  job_site_clean:false,
};

function StepHeading({
  number,
  title,
}:{
  number:number;
  title:string;
}){

  return (
    <div className="inspection-step-heading-5994">
      <span className="inspection-step-number-5994">
        {number}
      </span>
      <h3>{title}</h3>
    </div>
  );
}

function formatInspectionDate(value:string){

  const date=new Date(value);

  if(Number.isNaN(date.getTime()))return value;

  return date.toLocaleString('en-US',{
    timeZone:'America/New_York',
    dateStyle:'medium',
    timeStyle:'short',
  })+' ET';
}

export function IntegratedInstallationInspection6041({
  api,
  projectId,
  actorId,
  actorRole,
  csrfToken,
}:{
  api:Api;
  projectId:string;
  actorId:string;
  actorRole:string;
  csrfToken?:string;
}){

  const [workspace,setWorkspace]=useState<Workspace|null>(null);

  const [loading,setLoading]=useState(true);

  const [busy,setBusy]=useState(false);

  const [error,setError]=useState('');

  const [message,setMessage]=useState('');

  const [equipment,setEquipment]=useState<
    EquipmentConfirmation[]
  >([]);

  const [materials,setMaterials]=useState(false);

  const [quality,setQuality]=useState<
    Record<QualityKey,boolean>
  >({...EMPTY_QUALITY});

  const [impression,setImpression]=useState<
    'SATISFIED'|'UNSATISFIED'|''
  >('');

  const [notes,setNotes]=useState('');

  const [fictionalConfirmed,setFictionalConfirmed]=useState(false);

  const requestId=useRef(0);

  const submitting=useRef(false);

  const apiRef=useRef(api);

  apiRef.current=api;

  const endpoint=
    `integrated-installation-inspections/${projectId}/`;

  function applyWorkspace(value:Workspace){

    if(value.project_id!==projectId){

      throw new Error(
        'Inspection information does not match the selected project.'
      );
    }

    setWorkspace(value);

    const saved=value.saved_inspection;

    if(saved){

      setEquipment(
        saved.equipment.map(item=>({
          unit_id:item.unit_id,
          serial_number:item.serial_number,
          confirmed:item.confirmed,
        }))
      );

      setMaterials(
        saved.findings.required_materials_confirmed
      );

      setQuality({
        personally_inspected:
          saved.findings.personally_inspected,
        scope_completed_professionally:
          saved.findings.scope_completed_professionally,
        technician_delivered_quality_service:
          saved.findings.technician_delivered_quality_service,
        job_site_clean:
          saved.findings.job_site_clean,
      });

      setImpression(
        saved.findings.customer_impression
      );

      setNotes(saved.findings.inspection_notes);

      setFictionalConfirmed(
        saved.fictional_acceptance_test
      );

    }else{

      setEquipment(
        value.equipment_manifest.units.map(unit=>({
          unit_id:unit.unit_id,
          serial_number:
            unit.purchase_serial_number||'',
          confirmed:false,
        }))
      );

      setMaterials(false);

      setQuality({...EMPTY_QUALITY});

      setImpression('');

      setNotes('');

      setFictionalConfirmed(false);
    }
  }

  async function refresh(){

    const current=++requestId.current;

    setLoading(true);

    setError('');

    setMessage('');

    setWorkspace(null);

    try{

      const result=await apiRef.current<Workspace>(
        endpoint
      );

      if(current!==requestId.current)return;

      applyWorkspace(result);

    }catch(err){

      if(current===requestId.current){

        setError(
          err instanceof Error
            ?err.message
            :'Inspection information is unavailable.'
        );
      }

    }finally{

      if(current===requestId.current){

        setLoading(false);
      }
    }
  }

  useEffect(()=>{

    void refresh();

    return ()=>{

      requestId.current++;
    };

  },[projectId]);

  function updateEquipment(
    unitId:string,
    changes:Partial<EquipmentConfirmation>
  ){

    setEquipment(previous=>
      previous.map(item=>
        item.unit_id===unitId
          ?{...item,...changes}
          :item
      )
    );

    setMessage('');
  }

  const saved=workspace?.saved_inspection;

  const manifest=workspace?.equipment_manifest;

  const locked=Boolean(saved);

  const editable=Boolean(
    workspace?.can_record_inspection&&
    !locked&&
    !busy&&
    !loading
  );

  const confirmedCount=equipment.filter(
    item=>item.confirmed
  ).length;

  const selectedSerials=equipment
    .filter(item=>item.confirmed)
    .map(item=>
      item.serial_number.trim().toLowerCase()
    );

  const uniqueSerials=
    selectedSerials.length===
      new Set(selectedSerials).size;

  const allEquipmentConfirmed=Boolean(
    manifest?.available&&
    equipment.length>0&&
    equipment.length===manifest.units.length&&
    equipment.every(item=>
      item.confirmed&&
      Boolean(item.serial_number.trim())
    )&&
    uniqueSerials
  );

  const purchasesVerified=(
    manifest?.distributor_purchase_review_complete===true
  );

  const allQualityConfirmed=Object.values(
    quality
  ).every(Boolean);

  const canAccept=Boolean(
    editable&&
    fictionalConfirmed&&
    allEquipmentConfirmed&&
    materials&&
    purchasesVerified&&
    allQualityConfirmed&&
    impression==='SATISFIED'&&
    notes.trim().length<=2000
  );

  const canRequestCorrections=Boolean(
    editable&&
    fictionalConfirmed&&
    quality.personally_inspected&&
    impression!==''&&
    uniqueSerials&&
    notes.trim().length>=1&&
    notes.trim().length<=2000
  );

  async function submit(
    decision:'ACCEPT'|'CORRECTIONS_REQUIRED'
  ){

    if(
      submitting.current||
      !workspace||
      !editable||
      (
        decision==='ACCEPT'
          ?!canAccept
          :!canRequestCorrections
      )
    )return;

    const confirmed=window.confirm(
      decision==='ACCEPT'
        ?'Save this fictional installation acceptance test?'
        :'Save this fictional request for installation corrections?'
    );

    if(!confirmed)return;

    submitting.current=true;

    setBusy(true);

    setError('');

    setMessage('');

    const current=++requestId.current;

    const findings:Findings={
      equipment_and_serial_numbers_confirmed:
        allEquipmentConfirmed,
      required_materials_confirmed:materials,
      distributor_invoice_uploaded_and_verified:
        purchasesVerified,
      ...quality,
      customer_impression:impression,
      inspection_notes:notes.trim(),
      decision,
    };

    try{

      const result=await apiRef.current<Workspace>(
        endpoint,
        'POST',
        {
          expected_msr_id:workspace.msr_id,
          expected_snapshot_sha256:
            workspace.snapshot_sha256,
          expected_manifest_sha256:
            workspace.manifest_sha256,
          equipment_confirmations:
            equipment.map(item=>({
              unit_id:item.unit_id,
              serial_number:
                item.serial_number.trim(),
              confirmed:item.confirmed,
            })),
          findings,
          fictional_acceptance_test:true,
        }
      );

      if(current!==requestId.current)return;

      if(!result.saved_inspection){

        throw new Error(
          'The saved inspection could not be confirmed. Refresh before trying again.'
        );
      }

      applyWorkspace(result);

      setMessage(
        decision==='ACCEPT'
          ?'Fictional installation inspection saved.'
          :'Fictional correction request saved.'
      );

    }catch(err){

      if(current===requestId.current){

        setError(
          err instanceof Error
            ?err.message
            :'The inspection could not be saved.'
        );
      }

    }finally{

      submitting.current=false;

      setBusy(false);
    }
  }

  return (
    <section
      className="integrated-inspection-6041"
      aria-label="Installation inspection workspace"
    >

      <div className="inspection-heading-6041">

        <h2>Installation Inspection</h2>

        <button
          type="button"
          className="quiet"
          disabled={busy||loading}
          onClick={()=>{

            if(
              !locked&&
              (
                confirmedCount>0||
                materials||
                Object.values(quality).some(Boolean)||
                impression!==''||
                notes.trim()!==''||
                fictionalConfirmed
              )&&
              !window.confirm(
                'Refresh and discard unsaved inspection findings?'
              )
            )return;

            void refresh();
          }}
        >
          Refresh inspection
        </button>

      </div>

      {loading&&
        <p role="status">
          Loading approved project and equipment information...
        </p>}

      {error&&
        <p className="error" role="alert">{error}</p>}

      {message&&
        <p className="inspection-success-6041" role="status">
          {message}
        </p>}

      {workspace&&manifest&&<>

        <div className="inspection-project-6041">

          <h3>{workspace.customer_name}</h3>

          <p>{workspace.installation_address}</p>

          <p>
            {workspace.project_code}
            {' | Approved version '}
            {workspace.msr_version}.0
          </p>

        </div>

        <details className="inspection-instructions-6041">

          <summary>Instructions</summary>

          <p>
            Check the model and serial number of each
            installed equipment unit.
          </p>

          <p>
            Confirm the materials, work quality and
            customer impression.
          </p>

          <p>
            Accept the installation only when all
            requirements are satisfied. Otherwise,
            explain the deficiencies and request corrections.
          </p>

        </details>

        <div className="inspection-test-notice-6041">

          <strong>Fictional acceptance test</strong>

          <p>
            This development screen records fictional
            test findings only. It does not establish an
            actual physical inspection.
          </p>

          {!locked&&workspace.can_record_inspection&&
            <label className="inspection-check-6041">
              <input
                type="checkbox"
                checked={fictionalConfirmed}
                disabled={!editable}
                onChange={event=>
                  setFictionalConfirmed(
                    event.target.checked
                  )
                }
              />
              <span>
                I confirm this is a fictional acceptance test.
              </span>
            </label>}

        </div>

        {saved&&
          <div className="inspection-success-6041">

            <strong>{
              saved.status==='INTERNAL_ACCEPTANCE_CANDIDATE'
                ?'Fictional inspection recorded'
                :'Fictional corrections requested'
            }</strong>

            <p>
              Recorded: {
                formatInspectionDate(saved.recorded_at)
              }
            </p>

            <p>
              The saved inspection is retained.
              It cannot be overwritten here.
            </p>

          </div>}

        {!workspace.can_record_inspection&&!saved&&
          <p className="inspection-warning-6041">

            Inspection recording is not available for
            this project or its current equipment information.

          </p>}

        <div className="inspection-section-6041">

          <StepHeading
            number={1}
            title="Equipment and materials"
          />

          <p>
            Confirm the model and serial number of
            each installed unit.
          </p>

          <p className="inspection-count-6041">
            {confirmedCount} of {manifest.required_unit_count}
            {' equipment units confirmed'}
          </p>

          {!manifest.available&&
            <p className="inspection-warning-6041">
              Approved equipment information requires review.
            </p>}

          {manifest.units.map(unit=>{

            const item=equipment.find(
              value=>value.unit_id===unit.unit_id
            );

            if(!item)return null;

            const candidates=unit.serial_candidates;

            const serialEditable=(
              !unit.purchase_required||
              candidates.length>1
            );

            const validSerial=Boolean(
              item.serial_number.trim()&&
              (
                !unit.purchase_required||
                candidates.some(candidate=>
                  candidate.serial_number.toLowerCase()===
                  item.serial_number.trim().toLowerCase()
                )
              )
            );

            return (
              <div
                className="inspection-equipment-unit-6041"
                key={unit.unit_id}
              >

                <strong>{unit.model_number}</strong>

                {!unit.purchase_required&&
                  <small>
                    Existing equipment receiving service or repair
                  </small>}

                {locked?(
                  <p>
                    Serial number:
                    {' '}{item.serial_number||'Not confirmed'}
                  </p>
                ):serialEditable?(
                  unit.purchase_required?(
                    <label>
                      Select installed serial number
                      <select
                        value={item.serial_number}
                        disabled={!editable}
                        onChange={event=>
                          updateEquipment(
                            unit.unit_id,
                            {
                              serial_number:event.target.value,
                              confirmed:false,
                            }
                          )
                        }
                      >
                        <option value="">
                          Choose serial number
                        </option>

                        {candidates.map(candidate=>
                          <option
                            key={
                              candidate.allocation_id+
                              candidate.serial_number
                            }
                            value={candidate.serial_number}
                          >
                            {candidate.serial_number}
                          </option>
                        )}

                      </select>
                    </label>
                  ):(
                    <label>
                      Observed serial number
                      <input
                        value={item.serial_number}
                        maxLength={120}
                        disabled={!editable}
                        onChange={event=>
                          updateEquipment(
                            unit.unit_id,
                            {
                              serial_number:event.target.value,
                              confirmed:false,
                            }
                          )
                        }
                      />
                    </label>
                  )
                ):(
                  <p>
                    Serial number:
                    {' '}
                    {item.serial_number||
                      'Verified purchase serial required'}
                  </p>
                )}

                <label className="inspection-check-6041">

                  <input
                    type="checkbox"
                    checked={item.confirmed}
                    disabled={
                      !editable||!validSerial
                    }
                    onChange={event=>
                      updateEquipment(
                        unit.unit_id,
                        {
                          confirmed:event.target.checked
                        }
                      )
                    }
                  />

                  <span>
                    Model and serial number confirmed
                    at installation.
                  </span>

                </label>

                {!locked&&!validSerial&&
                  <small className="inspection-warning-text-6041">
                    Confirm the correct equipment identification
                    before accepting this unit.
                  </small>}

              </div>
            );
          })}

          {!uniqueSerials&&
            <p className="inspection-warning-6041">
              The same serial number cannot identify
              more than one equipment unit.
            </p>}

          <label className="inspection-check-6041">

            <input
              type="checkbox"
              checked={materials}
              disabled={!editable}
              onChange={event=>
                setMaterials(event.target.checked)
              }
            />

            <span>
              All required materials were installed.
            </span>

          </label>

          <div className="inspection-purchase-6041">

            <strong className={
              purchasesVerified
                ?'inspection-verified-6041'
                :'inspection-warning-text-6041'
            }>{
              purchasesVerified
                ?'Distributor invoices verified'
                :'Distributor invoice review outstanding'
            }</strong>

            <p>
              Verified purchasing records:
              {' '}
              {workspace.invoice_summary.filter(
                item=>
                  item.verification_status==='VERIFIED'&&
                  item.equipment_review_recorded
              ).length}
              {' of '}
              {workspace.invoice_summary.length}
            </p>

            <details>

              <summary>
                View distributor invoice details
              </summary>

              {workspace.invoice_summary.map(invoice=>
                <div
                  className="inspection-invoice-summary-6041"
                  key={invoice.allocation_id}
                >
                  <strong>
                    {invoice.distributor_name}
                  </strong>

                  <p>
                    Invoice {invoice.invoice_number}
                    {' | '}{invoice.invoice_date}
                  </p>

                  <p>{
                    invoice.verification_status==='VERIFIED'
                      ?'Verified'
                      :'Review required'
                  }</p>

                </div>
              )}

              {workspace.invoice_summary.length===0&&
                <p>No distributor invoices recorded.</p>}

              {!locked&&csrfToken&&
                <details>
                  <summary>
                    Manage distributor invoices
                  </summary>

                  <DistributorInvoiceWorkspace6007
                    api={api}
                    csrfToken={csrfToken}
                    actorId={actorId}
                    actorRole={actorRole}
                    initialProjectId={projectId}
                    fixedProject={true}
                  />

                  <p>
                    After updating distributor invoices,
                    select Refresh inspection above.
                    Unsaved inspection confirmations
                    will need to be entered again.
                  </p>

                </details>}

            </details>

          </div>

          {manifest.warnings.length>0&&
            <details className="inspection-instructions-6041">

              <summary>Equipment review information</summary>

              {manifest.warnings.map((warning,index)=>
                <p key={index}>{warning}</p>
              )}

            </details>}

        </div>

        <div className="inspection-section-6041">

          <StepHeading
            number={2}
            title="Installation quality"
          />

          {QUALITY_QUESTIONS.map(([key,label])=>
            <label
              key={key}
              className="inspection-check-6041"
            >

              <input
                type="checkbox"
                checked={quality[key]}
                disabled={!editable}
                onChange={event=>
                  setQuality(previous=>({
                    ...previous,
                    [key]:event.target.checked,
                  }))
                }
              />

              <span>{label}</span>

            </label>
          )}

          <fieldset className="inspection-impression-6041">

            <legend>Customer impression</legend>

            <label className="inspection-check-6041">

              <input
                type="radio"
                name={`impression-${projectId}`}
                checked={impression==='SATISFIED'}
                disabled={!editable}
                onChange={()=>setImpression('SATISFIED')}
              />

              <span>Satisfied</span>

            </label>

            <label className="inspection-check-6041">

              <input
                type="radio"
                name={`impression-${projectId}`}
                checked={impression==='UNSATISFIED'}
                disabled={!editable}
                onChange={()=>setImpression('UNSATISFIED')}
              />

              <span>Unsatisfied</span>

            </label>

          </fieldset>

          <label className="inspection-notes-6041">

            Inspection notes
            {' '}
            {impression==='UNSATISFIED'
              ?'(required)'
              :'(optional for acceptance)'}

            <textarea
              value={notes}
              rows={4}
              maxLength={2000}
              disabled={!editable}
              placeholder={
                'Describe deficiencies or additional observations.'
              }
              onChange={event=>
                setNotes(event.target.value)
              }
            />

          </label>

        </div>

        <div className="inspection-section-6041">

          <StepHeading
            number={3}
            title="Installation acceptance"
          />

          {saved?(
            <div className="inspection-success-6041">

              <strong>{
                saved.status==='INTERNAL_ACCEPTANCE_CANDIDATE'
                  ?'Fictional acceptance recorded'
                  :'Corrections requested'
              }</strong>

              <p>
                Saved findings are available above.
              </p>

              {saved.status==='CORRECTIONS_REQUIRED'&&
                <p>
                  A controlled reinspection is required
                  before a subsequent acceptance.
                </p>}

            </div>
          ):(
            <>

              <div className="inspection-actions-6041">

                <button
                  type="button"
                  disabled={!canAccept}
                  onClick={()=>void submit('ACCEPT')}
                >
                  {busy?'Saving...':'Accept installation'}
                </button>

                <button
                  type="button"
                  className="quiet"
                  disabled={!canRequestCorrections}
                  onClick={()=>void submit(
                    'CORRECTIONS_REQUIRED'
                  )}
                >
                  Request corrections
                </button>

              </div>

              {!canAccept&&
                <p className="inspection-action-help-6041">
                  Confirm every equipment unit, all required
                  materials, verified distributor invoices,
                  installation quality and customer satisfaction
                  before accepting.
                </p>}

              <p className="inspection-action-help-6041">
                To request corrections, confirm the inspection
                was performed, select the customer impression
                and describe the deficiencies in the notes.
              </p>

              {error&&
                <p className="error" role="alert">{error}</p>}

            </>
          )}

        </div>

        <div className="inspection-section-6041">

          <StepHeading
            number={4}
            title="Completion Certificate"
          />

          {saved&&
            saved.status==='INTERNAL_ACCEPTANCE_CANDIDATE'&&
            saved.fictional_acceptance_test===true&&
            <CompletionCertificatePreview6049
              key={`${projectId}-${workspace.msr_id}-${saved.inspection_id}`}
              api={api}
              projectId={projectId}
              msrId={workspace.msr_id}
              inspectionId={saved.inspection_id}
            />}

          {!saved&&
            <p>
              Record the inspection before preparing
              the Completion Certificate.
            </p>}

          {saved&&saved.status==='CORRECTIONS_REQUIRED'&&
            <p>
              Resolve the recorded deficiencies before
              preparing a Completion Certificate.
            </p>}


          <button type="button" disabled>

            Send Completion Certificate

          </button>

          <p className="inspection-action-help-6041">

            Certificate sending remains unavailable until
            the required installation evidence and DocuSign
            safeguards are established.

          </p>

        </div>

      </>}

    </section>
  );
}
