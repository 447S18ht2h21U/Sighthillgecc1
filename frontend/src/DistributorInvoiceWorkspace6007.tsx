import DistributorEquipmentComparison6026, {
  EquipmentModelHint6026,
  type ProjectEquipmentReconciliation6026,
} from './DistributorEquipmentComparison6026';

import React, {useEffect, useState} from 'react';

type Api = <T>(
  path:string,
  method?:string,
  data?:unknown
)=>Promise<T>;

type Project = {
  id:string;
  code:string;
  customer_name:string;
  location:string;
  state:string;
};

type Schedule = {
  project:string;
  installation_manager:string;
  status:string;
};

type Page<T> = {
  results:T[];
  next:string|null;
};

type RetainedEquipment = {
  quantity:number;
  model_number:string;
  serial_numbers:string[];
};

type Invoice = {
  equipment_review_recorded:boolean;
  equipment_rows:RetainedEquipment[];
  no_equipment_on_invoice:boolean;
  invoice_id:string;
  allocation_id:string;
  msr_id:string;
  current_version:boolean;
  distributor_name:string;
  invoice_number:string;
  invoice_date:string;
  invoice_total:string;
  filename:string;
  equipment_amount:string;
  material_amount:string;
  other_amount:string;
  allocated_total:string;
  allocation_notes:string;
  verification_status:string;
  verified_at:string|null;
  review_notes:string;
  original_document_url:string;
};

type Workspace = {
  equipment_reconciliation?:ProjectEquipmentReconciliation6026;
  project_id:string;
  project_code:string;
  customer_name:string;
  installation_address:string;
  msr_id:string;
  msr_version:number;
  can_upload:boolean;
  can_verify:boolean;
  can_allocate:boolean;
  invoices:Invoice[];
  current_invoice_count:number;
  recorded_verifications_complete:boolean;
};

type ExtractedField = {
  value:string|null;
  candidates:string[];
  status:string;
};

type EquipmentCandidate = {
  model_number:string|null;
  serial_number_candidates:string[];
  quantity_candidates:number[];
};

type EditableEquipment = {
  quantity:string;
  model_number:string;
  serial_number:string;
};

type InvoiceExtraction = {
  fields:Record<string,ExtractedField>;
  equipment_candidates:EquipmentCandidate[];
  warnings:string[];
  project_id:string;
  msr_id:string;
  document_sha256:string;
};

type InvoiceDetails = {
  distributor_name:string;
  invoice_number:string;
  invoice_date:string;
  invoice_total:string;
};

const EMPTY_INVOICE_DETAILS:InvoiceDetails = {
  distributor_name:'',
  invoice_number:'',
  invoice_date:'',
  invoice_total:'',
};

type Props = {
  api:Api;
  csrfToken:string;
  actorId:string;
  actorRole:string;
  initialProjectId?:string;
  fixedProject?:boolean;
};

async function readPages<T>(
  api:Api,
  path:string
):Promise<T[]> {
  const rows:T[]=[];

  for(let page=1;page<=100;page++){
    const response=await api<Page<T>|T[]>(
      `${path}?page=${page}`
    );

    if(Array.isArray(response)){
      return response;
    }

    rows.push(...response.results);

    if(!response.next)return rows;
  }

  throw new Error(
    'Too many records to display. Contact your manager.'
  );
}

function money(value:string){
  const number=Number(value);

  return Number.isFinite(number)
    ? number.toLocaleString('en-US',{
        style:'currency',
        currency:'USD'
      })
    : 'Unavailable';
}

function statusLabel(status:string){
  const labels:Record<string,string>={
    NOT_VERIFIED:'Awaiting verification',
    VERIFIED:'Verified',
    REJECTED:'Corrections required',
    REQUIRES_REVIEW:'Review required',
    HISTORICAL_VERSION:'Earlier approved project version',
  };

  return labels[status]||'Review required';
}

function InvoiceReview({
  invoice,
  workspace,
  api,
  disabled,
  onChanged,
  onBusy,
}:{
  invoice:Invoice;
  workspace:Workspace;
  api:Api;
  disabled:boolean;
  onChanged:(value:Workspace)=>void;
  onBusy:(value:boolean)=>void;
}){
  const [examined,setExamined]=useState(false);
  const [confirmed,setConfirmed]=useState(false);
  const [notes,setNotes]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');

  async function review(accept:boolean){
    if(busy||disabled)return;

    if(accept&&(!examined||!confirmed))return;

    if(!accept&&!notes.trim()){
      setError('Explain why the invoice cannot be verified.');
      return;
    }

    if(!window.confirm(
      accept
        ? 'Save this invoice verification? The decision will be retained in the audit history.'
        : 'Record that this invoice requires corrections? Contact the Comptroller to resolve it.'
    ))return;

    setBusy(true);
    onBusy(true);
    setError('');

    try{
      const result=await api<Workspace>(
        `distributor-invoices/${workspace.project_id}/${invoice.allocation_id}/review/`,
        'POST',
        {
          expected_msr_id:workspace.msr_id,
          invoice_examined:examined,
          allocation_confirmed:confirmed,
          accept,
          review_notes:notes.trim(),
        }
      );

      onChanged(result);
    }catch(e){
      setError((e as Error).message);
    }finally{
      setBusy(false);
      onBusy(false);
    }
  }

  return <fieldset disabled={busy||disabled}
    className="invoice-review-6007">

    <legend>Verify invoice</legend>

    <label className="invoice-check-6007">
      <input type="checkbox"
        checked={examined}
        onChange={e=>setExamined(e.target.checked)}/>
      <span>I reviewed the original distributor invoice.</span>
    </label>

    <label className="invoice-check-6007">
      <input type="checkbox"
        checked={confirmed}
        onChange={e=>setConfirmed(e.target.checked)}/>
      <span>I confirmed the costs assigned to this project.</span>
    </label>

    <label>Review notes
      <textarea maxLength={2000}
        value={notes}
        onChange={e=>setNotes(e.target.value)}/>
      <small>Required if corrections are needed.</small>
    </label>

    {error&&<p className="error" role="alert">{error}</p>}

    <div className="invoice-actions-6007">
      <button type="button"
        disabled={busy||disabled||!examined||!confirmed}
        onClick={()=>void review(true)}>
        Verify Invoice
      </button>

      <button type="button" className="quiet"
        disabled={busy||disabled||!notes.trim()}
        onClick={()=>void review(false)}>
        Request corrections
      </button>
    </div>
  </fieldset>;
}

export function DistributorInvoiceWorkspace6007({
  api,
  csrfToken,
  actorId,
  actorRole,
  initialProjectId='',
  fixedProject=false,
}:Props){

  const [projects,setProjects]=useState<Project[]>([]);
  const [projectId,setProjectId]=useState(initialProjectId);
  const [workspace,setWorkspace]=useState<Workspace|null>(null);
  const [loadingProjects,setLoadingProjects]=useState(!fixedProject);
  const [loading,setLoading]=useState(false);
  const [busy,setBusy]=useState(false);
  const [reviewBusy,setReviewBusy]=useState(false);
  const [error,setError]=useState('');
  const [success,setSuccess]=useState('');
  const [reload,setReload]=useState(0);

  const [showUpload,setShowUpload]=useState(false);
  const [file,setFile]=useState<File|null>(null);
  const [fileKey,setFileKey]=useState(0);

  const [details,setDetails]=useState<InvoiceDetails>(
    EMPTY_INVOICE_DETAILS
  );

  const [extraction,setExtraction]=
    useState<InvoiceExtraction|null>(null);

  const [equipmentRows,setEquipmentRows]=
    useState<EditableEquipment[]>([]);

  const [equipmentConfirmed,setEquipmentConfirmed]=
    useState(false);

  const [noEquipment,setNoEquipment]=useState(false);

  const [reading,setReading]=useState(false);

  const [readingMessage,setReadingMessage]=useState('');

  const [detailsConfirmed,setDetailsConfirmed]=useState(false);

  const [vendorConfirmed,setVendorConfirmed]=useState(false);

  const blocked=busy||reviewBusy||loading||reading;

  useEffect(()=>{
    if(fixedProject)return;

    let cancelled=false;

    setLoadingProjects(true);
    setError('');

    void (async()=>{
      try{
        const rows=await readPages<Project>(
          api,'operational-projects/'
        );

        let allowed=rows.filter(
          project=>project.state!=='CANCELLED'
        );

        if(actorRole==='INSTALLATION_MANAGER'){
          const schedules=await readPages<Schedule>(
            api,'installation-schedules/'
          );

          const assigned=new Set(
            schedules.filter(
              schedule=>
                schedule.installation_manager===actorId&&
                ['SCHEDULED','COMPLETED'].includes(
                  schedule.status
                )
            ).map(schedule=>schedule.project)
          );

          allowed=allowed.filter(
            project=>assigned.has(project.id)
          );
        }

        if(cancelled)return;

        setProjects(allowed);
      }catch(e){
        if(!cancelled)setError((e as Error).message);
      }finally{
        if(!cancelled)setLoadingProjects(false);
      }
    })();

    return()=>{cancelled=true;};
  },[actorId,actorRole,fixedProject,reload]);

  useEffect(()=>{
    let cancelled=false;

    setWorkspace(null);
    setFile(null);
    setDetails(EMPTY_INVOICE_DETAILS);
    setExtraction(null);
    setEquipmentRows([]);
    setNoEquipment(false);
    setEquipmentConfirmed(false);
    setDetailsConfirmed(false);
    setVendorConfirmed(false);
    setReadingMessage('');
    setShowUpload(false);
    setSuccess('');

    if(!projectId){
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');

    void api<Workspace>(
      `distributor-invoices/${projectId}/`
    ).then(result=>{
      if(!cancelled)setWorkspace(result);
    }).catch(e=>{
      if(!cancelled)setError((e as Error).message);
    }).finally(()=>{
      if(!cancelled)setLoading(false);
    });

    return()=>{cancelled=true;};
  },[projectId,actorId,reload]);

  useEffect(()=>{
    if(!showUpload&&!busy&&!reviewBusy)return;

    function warn(event:BeforeUnloadEvent){
      event.preventDefault();
      event.returnValue='';
    }

    window.addEventListener('beforeunload',warn);

    return()=>window.removeEventListener(
      'beforeunload',warn
    );
  },[showUpload,busy,reviewBusy]);

  function chooseProject(id:string){
    if(blocked)return;

    if(showUpload&&!window.confirm(
      'Leave this invoice without saving?'
    ))return;

    setProjectId(id);
    setError('');
  }

  async function chooseFile(value:File|null){
    setError('');

    if(!value||!workspace||blocked)return;

    if(!workspace.can_upload)return;

    if(
      !['application/pdf','image/jpeg','image/png']
        .includes(value.type)||
      value.size<=0||
      value.size>15*1024*1024
    ){
      setFile(null);
      setFileKey(value=>value+1);

      setError(
        'Choose a PDF, JPEG or PNG file up to 15 MB.'
      );

      return;
    }

    setFile(value);

    setDetails(EMPTY_INVOICE_DETAILS);
    setExtraction(null);
    setEquipmentRows([]);
    setNoEquipment(false);
    setEquipmentConfirmed(false);
    setDetailsConfirmed(false);
    setVendorConfirmed(false);
    setReading(true);
    setReadingMessage('Reading invoice...');

    const form=new FormData();

    form.set('document',value,value.name);

    form.set('expected_msr_id',workspace.msr_id);

    try{

      const response=await fetch(
        `/api/distributor-invoices/${workspace.project_id}/extract/`,
        {
          method:'POST',
          credentials:'same-origin',
          headers:{
            'X-CSRFToken':csrfToken
          },
          body:form,
        }
      );

      if(!(
        response.headers.get('content-type')||''
      ).includes('application/json')){
        throw new Error(
          'Automatic reading is unavailable.'
        );
      }

      const result=await response.json();

      if(!response.ok){
        throw new Error(
          typeof result.detail==='string'
            ?result.detail
            :JSON.stringify(result)
        );
      }

      const extracted=result as InvoiceExtraction;

      if(
        extracted.project_id!==workspace.project_id||
        extracted.msr_id!==workspace.msr_id
      ){
        throw new Error(
          'The selected project changed. Refresh and try again.'
        );
      }

      setExtraction(extracted);

      setEquipmentRows(
        extracted.equipment_candidates.map(row=>({
          quantity:
            row.quantity_candidates.length===1
              ?String(row.quantity_candidates[0])
              :'',
          model_number:row.model_number||'',
          serial_number:
            row.serial_number_candidates.join(', '),
        }))
      );

      setEquipmentConfirmed(false);

      setDetails({
        distributor_name:
          extracted.fields.distributor_name?.value||'',
        invoice_number:
          extracted.fields.invoice_number?.value||'',
        invoice_date:
          extracted.fields.invoice_date?.value||'',
        invoice_total:
          extracted.fields.invoice_total?.value||'',
      });

      const found=Object.values(extracted.fields).filter(
        field=>field.value!==null
      ).length;

      const incompleteEquipment=
        extracted.equipment_candidates.some(row=>
          !row.model_number||
          row.quantity_candidates.length!==1||
          row.serial_number_candidates.length===0
        );

      setReadingMessage(
        found===4&&
        extracted.equipment_candidates.length>0&&
        !incompleteEquipment
          ?'Invoice read. Review and correct the suggested information.'
          :`Invoice partially read. ${found} of 4 invoice details found. Review missing information below.`
      );

    }catch(e){

      setReadingMessage(
        'Automatic reading could not complete. '+
        'You can enter the information manually. '+
        (e as Error).message
      );

    }finally{

      setReading(false);

    }
  }

  function changeDetail(
    field:keyof InvoiceDetails,
    value:string
  ){

    setDetails(previous=>({
      ...previous,
      [field]:value,
    }));

    setDetailsConfirmed(false);
  }

  function editEquipment(
    index:number,
    field:keyof EditableEquipment,
    value:string
  ){

    setEquipmentRows(previous=>
      previous.map((row,rowIndex)=>
        rowIndex===index
          ?{...row,[field]:value}
          :row
      )
    );

    setEquipmentConfirmed(false);
  }

  function addEquipment(){

    setNoEquipment(false);

    setEquipmentRows(previous=>[
      ...previous,
      {
        quantity:'1',
        model_number:'',
        serial_number:'',
      }
    ]);

    setEquipmentConfirmed(false);
  }

  function removeEquipment(index:number){

    setEquipmentRows(previous=>
      previous.filter((_,rowIndex)=>rowIndex!==index)
    );

    setEquipmentConfirmed(false);
  }

  function serialNumbers(value:string){
    return value.split(/[,;\n]/)
      .map(item=>item.trim())
      .filter(Boolean);
  }

  const allSerials=equipmentRows.flatMap(row=>
    serialNumbers(row.serial_number)
      .map(serial=>serial.toLowerCase())
  );

  const duplicateSerials=
    new Set(allSerials).size!==allSerials.length;

  const incompleteEquipmentRows=
    duplicateSerials||
    equipmentRows.length>250||
    allSerials.length>1000||
    equipmentRows.some(row=>
      !/^[1-9][0-9]{0,3}$/.test(row.quantity.trim())||
      Number(row.quantity)>1000||
      !row.model_number.trim()||
      serialNumbers(row.serial_number).length
        !==Number(row.quantity)
    );

  const equipmentReady=
    equipmentConfirmed&&
    !incompleteEquipmentRows&&
    (
      equipmentRows.length>0
        ?!noEquipment
        :noEquipment
    );

  async function upload(
    event:React.FormEvent<HTMLFormElement>
  ){
    event.preventDefault();

    if(
      blocked||
      !workspace||
      !workspace.can_upload||
      !file||
      !detailsConfirmed||
      !vendorConfirmed
    )return;

    if(!equipmentReady){

      setError(
        'Complete and confirm the equipment information before saving.'
      );

      return;
    }

    const form=new FormData(event.currentTarget);

    form.set('document',file,file.name);
    form.set('expected_msr_id',workspace.msr_id);

    form.set(
      'equipment_rows',
      JSON.stringify(
        equipmentRows.map(row=>({
          quantity:Number(row.quantity),
          model_number:row.model_number.trim(),
          serial_numbers:serialNumbers(row.serial_number),
        }))
      )
    );

    form.set(
      'no_equipment_on_invoice',
      String(noEquipment)
    );

    form.set(
      'distributor_invoice_confirmed',
      String(vendorConfirmed)
    );

    form.set(
      'invoice_details_confirmed',
      String(detailsConfirmed)
    );

    form.set(
      'equipment_information_confirmed',
      String(equipmentConfirmed)
    );

    setBusy(true);
    setError('');
    setSuccess('');

    try{
      const response=await fetch(
        `/api/distributor-invoices/${workspace.project_id}/`,
        {
          method:'POST',
          credentials:'same-origin',
          headers:{
            'X-CSRFToken':csrfToken
          },
          body:form,
        }
      );

      const contentType=response.headers.get('content-type')||'';

      if(!contentType.includes('application/json')){
        throw new Error(
          'The server returned an unexpected response. Refresh and check existing invoices before trying again.'
        );
      }

      const result=await response.json();

      if(!response.ok){
        throw new Error(
          typeof result.detail==='string'
            ?result.detail
            :JSON.stringify(result)
        );
      }

      setWorkspace(result as Workspace);
      setDetails(EMPTY_INVOICE_DETAILS);
      setExtraction(null);
    setEquipmentRows([]);
    setNoEquipment(false);
    setEquipmentConfirmed(false);
      setDetailsConfirmed(false);
      setVendorConfirmed(false);
      setReadingMessage('');
      setFile(null);
      setFileKey(value=>value+1);
      setShowUpload(false);

      setSuccess(
        'Invoice and reviewed equipment saved. Purchase verification is still required.'
      );

    }catch(e){
      setError((e as Error).message);
    }finally{
      setBusy(false);
    }
  }

  const currentInvoices=workspace?.invoices.filter(
    invoice=>invoice.current_version
  )||[];

  const historicalInvoices=workspace?.invoices.filter(
    invoice=>!invoice.current_version
  )||[];

  function displayInvoice(invoice:Invoice){
    return <article key={invoice.allocation_id}
      className="invoice-record-6007">

      <div className="invoice-record-heading-6007">
        <div>
          <strong>{invoice.distributor_name}</strong>
          <div>Invoice {invoice.invoice_number}</div>
          <small>{invoice.invoice_date}</small>
        </div>

        <strong className={
          invoice.verification_status==='VERIFIED'
            ?'invoice-status-verified-6007'
            :'invoice-status-pending-6007'
        }>
          {statusLabel(invoice.verification_status)}
        </strong>
      </div>

      <dl className="invoice-costs-6007">
        <dt>Original invoice total</dt>
        <dd>{money(invoice.invoice_total)}</dd>

        <dt>Equipment</dt>
        <dd>{money(invoice.equipment_amount)}</dd>

        <dt>Materials</dt>
        <dd>{money(invoice.material_amount)}</dd>

        {Number(invoice.other_amount)>0&&<>
          <dt>Other costs</dt>
          <dd>{money(invoice.other_amount)}</dd>
        </>}

        <dt><strong>Total for this project</strong></dt>
        <dd><strong>{money(invoice.allocated_total)}</strong></dd>
      </dl>

      {invoice.allocation_notes&&
        <p>{invoice.allocation_notes}</p>}

      {invoice.equipment_review_recorded?(
        <div className="invoice-extraction-review-6013">

          <h3>Recorded equipment information</h3>

          {invoice.no_equipment_on_invoice?(
            <p>No equipment in this project allocation.</p>
          ):(
            <div style={{overflowX:'auto'}}>
              <table>
                <thead>
                  <tr>
                    <th>Quantity</th>
                    <th>Model number</th>
                    <th>Serial number(s)</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.equipment_rows.map((row,index)=>
                    <tr key={index}>
                      <td>{row.quantity}</td>
                      <td>{row.model_number}</td>
                      <td>{row.serial_numbers.join(', ')}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          <p className="muted">
            Purchased equipment information.
            Physical installation must be confirmed separately.
          </p>

        </div>
      ):(
        <p className="invoice-warning-6007">
          Equipment information review is outstanding.
        </p>
      )}

      <p>
        <a href={invoice.original_document_url}
          download={invoice.filename}>
          Download original invoice
        </a>
      </p>

      {invoice.review_notes&&
        <p>Review notes: {invoice.review_notes}</p>}

      {invoice.verified_at&&
        <p className="muted">
          Review recorded: {
            new Date(invoice.verified_at).toLocaleString(
              'en-US',{timeZone:'America/New_York'}
            )
          } ET
        </p>}

      {invoice.current_version&&
       invoice.verification_status==='REJECTED'&&
        <p className="invoice-warning-6007">
          Contact the Comptroller to resolve this invoice.
          The original decision is retained.
        </p>}

      {workspace&&
       workspace.can_verify&&
       invoice.current_version&&
       invoice.verification_status==='NOT_VERIFIED'&&
       invoice.equipment_review_recorded&&
        <InvoiceReview
          key={invoice.allocation_id}
          invoice={invoice}
          workspace={workspace}
          api={api}
          disabled={busy||loading||showUpload}
          onBusy={setReviewBusy}
          onChanged={result=>{
            setWorkspace(result);
            setSuccess('Invoice review recorded.');
          }}
        />}
    </article>;
  }

  return <section className="invoice-workspace-6007">

    <h2>Distributor invoices</h2>

    {!fixedProject&&<>

      <label>Select project
        <select value={projectId}
          disabled={blocked||loadingProjects}
          onChange={e=>chooseProject(e.target.value)}>

          <option value="">Choose a project</option>

          {projects.map(project=>
            <option key={project.id} value={project.id}>
              {project.customer_name} | {project.code} |
              {' '}{project.location}
            </option>
          )}
        </select>
      </label>

      {loadingProjects&&
        <p role="status">Loading projects...</p>}

      {!loadingProjects&&!projects.length&&
        <p>No eligible assigned projects were found.</p>}

    </>}

    <button type="button" className="quiet"
      disabled={blocked}
      onClick={()=>{
        if(showUpload&&!window.confirm(
          'Refresh without saving the invoice?'
        ))return;

        setReload(value=>value+1);
      }}>
      Refresh
    </button>

    {loading&&<p role="status">Loading invoices...</p>}

    {error&&<p role="alert" className="error">{error}</p>}

    {success&&
      <p role="status" className="invoice-success-6007">
        {success}
      </p>}

    {workspace&&<>

      <div className="invoice-project-6007">
        <strong>{workspace.customer_name}</strong>
        <div>{workspace.installation_address}</div>
        <small>
          {workspace.project_code} | Approved version
          {' '}{workspace.msr_version}.0
        </small>
      </div>

      <DistributorEquipmentComparison6026
          reconciliation={workspace.equipment_reconciliation}/>

        <div className="invoice-summary-6007">
        <strong>
          Distributor invoices: {workspace.current_invoice_count}
        </strong>

        <span>
          {workspace.current_invoice_count===0
            ?'Invoice required'
            :workspace.recorded_verifications_complete
              ?'Recorded invoice reviews complete'
              :'Invoice verification outstanding'}
        </span>
      </div>

      {currentInvoices.length===0&&
        <p>No distributor invoices have been recorded.</p>}

      {currentInvoices.map(displayInvoice)}

      {workspace.can_upload&&!showUpload&&
        <button type="button" disabled={blocked}
          onClick={()=>{
            setShowUpload(true);
            setSuccess('');
            setError('');
          }}>
          Upload distributor invoice
        </button>}

      {showUpload&&workspace.can_upload&&
        <form onChange={event=>{
        const target:EventTarget=event.target;

        if(
          !(target instanceof HTMLInputElement)&&
          !(target instanceof HTMLTextAreaElement)
        )return;

        if([
          'equipment_amount',
          'material_amount',
          'other_amount',
          'allocation_notes'
        ].includes(target.name)){
          setDetailsConfirmed(false);
        }
      }}
      onSubmit={event=>void upload(event)}
          className="invoice-upload-6007">

          <fieldset disabled={busy||reviewBusy||reading}>

            <legend>Upload distributor invoice</legend>

            <div className="invoice-upload-options-6007">

              <label>
                Take Picture of Invoice
                <input key={`camera-${fileKey}`}
                  type="file"
                  accept="image/jpeg,image/png"
                  capture="environment"
                  onChange={event=>chooseFile(
                    event.target.files?.[0]||null
                  )}/>
              </label>

              <label>
                Choose Existing File
                <input key={`file-${fileKey}`}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={event=>chooseFile(
                    event.target.files?.[0]||null
                  )}/>
              </label>

            </div>

            {file?
              <p><strong>Selected file:</strong> {file.name}</p>:
              <p className="muted">PDF, JPEG or PNG. Maximum 15 MB.</p>}

            {readingMessage&&
              <p role="status"
                className="invoice-reading-6013">
                {readingMessage}
              </p>}

            {extraction&&
              <details className="invoice-extraction-review-6013">
                <summary>Information requiring review</summary>
                {extraction.warnings.map((warning,index)=>
                  <p key={index}>{warning}</p>
                )}
              </details>}

            <h3>Review invoice details</h3>

            <div className="grid">

              <label>Distributor
                <input name="distributor_name"
                  required maxLength={250}
                  value={details.distributor_name}
                  onChange={e=>changeDetail(
                    'distributor_name',e.target.value
                  )}/>
              </label>

              <label>Invoice number
                <input name="invoice_number"
                  required maxLength={150}
                  value={details.invoice_number}
                  onChange={e=>changeDetail(
                    'invoice_number',e.target.value
                  )}/>
              </label>

              <label>Invoice date
                <input name="invoice_date"
                  type="date" required
                  value={details.invoice_date}
                  onChange={e=>changeDetail(
                    'invoice_date',e.target.value
                  )}/>
              </label>

              <label>Original invoice total ($)
                <input name="invoice_total"
                  type="number" min="0.01"
                  step="0.01" max="9999999999.99"
                  value={details.invoice_total}
                  onChange={e=>changeDetail(
                    'invoice_total',e.target.value
                  )}
                  required/>
              </label>

              <h3 style={{gridColumn:'1 / -1'}}>
                Internal GECC purchase costs
              </h3>

              <p className="muted"
                style={{gridColumn:'1 / -1'}}>
                These costs are confidential. They do not
                change the customer's approved selling price.
              </p>

              <label>Equipment for this project ($)
                <input name="equipment_amount"
                  type="number" min="0"
                  step="0.01" max="9999999999.99"
                  defaultValue="0.00" required/>
              </label>

              <label>Materials for this project ($)
                <input name="material_amount"
                  type="number" min="0"
                  step="0.01" max="9999999999.99"
                  defaultValue="0.00" required/>
              </label>

              <label>Other costs for this project ($)
                <input name="other_amount"
                  type="number" min="0"
                  step="0.01" max="9999999999.99"
                  defaultValue="0.00" required/>
              </label>

              <label>Allocation notes
                <textarea name="allocation_notes"
                  maxLength={2000}/>
                <small>Required for other costs.</small>
              </label>

            </div>

            <p className="muted">
              Enter only the costs belonging to this project.
              The Comptroller or CEO can allocate the
              remaining costs to other projects.
            </p>

            {file&&!reading&&
              <div className="invoice-extraction-review-6013">

                <h3>Review equipment information</h3>

                <p>
                  Check each quantity, model number and serial
                  number against the original invoice.
                  Correct any reading errors below.
                </p>

                {equipmentRows.length===0&&
                  <p className="muted">
                    No equipment rows were identified.
                    Add equipment manually if needed.
                  </p>}

                {equipmentRows.length>0&&
                  <div style={{overflowX:'auto'}}>
                    <table className="invoice-equipment-6018">
                      <thead>
                        <tr>
                          <th>Quantity</th>
                          <th>Model number</th>
                          <th>Serial number(s)</th>
                          <th>Action</th>
                        </tr>
                      </thead>

                      <tbody>
                        {equipmentRows.map((row,index)=>
                          <tr key={index}>
                            <td>
                              <input
                                aria-label={`Equipment ${index+1} quantity`}
                                type="number"
                                min="1"
                                max="99999"
                                step="1"
                                value={row.quantity}
                                onChange={event=>editEquipment(
                                  index,
                                  'quantity',
                                  event.target.value
                                )}/>
                            </td>
                            <td>
                              <input
                                aria-label={`Equipment ${index+1} model number`}
                                maxLength={100}
                                value={row.model_number}
                                onChange={event=>editEquipment(
                                  index,
                                  'model_number',
                                  event.target.value
                                )}/>

                              <EquipmentModelHint6026
                                model={row.model_number}
                                reconciliation={
                                  workspace.equipment_reconciliation
                                }/>

                            </td>
                            <td>
                              <input
                                aria-label={`Equipment ${index+1} serial numbers`}
                                maxLength={2000}
                                value={row.serial_number}
                                onChange={event=>editEquipment(
                                  index,
                                  'serial_number',
                                  event.target.value
                                )}/>
                            </td>
                            <td>
                              <button
                                type="button"
                                className="quiet"
                                aria-label={`Remove equipment ${index+1}`}
                                onClick={()=>removeEquipment(index)}>
                                Remove
                              </button>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>}

                <button type="button"
                  className="quiet"
                  onClick={addEquipment}>
                  + Add equipment
                </button>

                {incompleteEquipmentRows&&
                  <p className="invoice-warning-6007">
                    Some equipment information is incomplete.
                    Review the original invoice before confirming.
                  </p>}

                {equipmentRows.length===0&&
                  <label className="invoice-check-6007">
                    <input type="checkbox"
                      checked={noEquipment}
                      onChange={event=>{
                        setNoEquipment(event.target.checked);
                        setEquipmentConfirmed(false);
                      }}/>
                    <span>
                      No equipment is included in this
                      project invoice allocation.
                    </span>
                  </label>}

                {(equipmentRows.length>0||noEquipment)&&
                  <label className="invoice-check-6007">
                    <input type="checkbox"
                      checked={equipmentConfirmed}
                      disabled={incompleteEquipmentRows}
                      onChange={event=>setEquipmentConfirmed(
                        event.target.checked
                      )}/>
                    <span>
                      {noEquipment
                        ?'I reviewed the original invoice and confirmed this allocation contains no equipment.'
                        :'I checked these quantities, model numbers and serial numbers against the original invoice.'}
                    </span>
                  </label>}

                <p className="muted">
                  Only quantities, model numbers and serial numbers
                  may carry forward from distributor invoices to
                  customer equipment records. Distributor prices
                  remain confidential.
                </p>

                <p className="muted">
                  Confirmed equipment information will be saved
                  with the original invoice and approved
                  project version.
                </p>

              </div>}

            <div className="invoice-extraction-review-6013">

              <label className="invoice-check-6007">
                <input type="checkbox"
                  checked={vendorConfirmed}
                  onChange={e=>setVendorConfirmed(
                    e.target.checked
                  )}/>
                <span>
                  This is a distributor invoice issued to GECC.
                </span>
              </label>

              <label className="invoice-check-6007">
                <input type="checkbox"
                  checked={detailsConfirmed}
                  onChange={e=>setDetailsConfirmed(
                    e.target.checked
                  )}/>
                <span>
                  I reviewed and confirmed the invoice details.
                </span>
              </label>

            </div>

            <div className="invoice-actions-6007">

              <button type="submit"
                disabled={
                  busy||reviewBusy||reading||!file||
                  !detailsConfirmed||!vendorConfirmed||
                  !equipmentReady
                }>
                {busy?'Saving invoice...':'Save Invoice'}
              </button>

              <button type="button" className="quiet"
                disabled={busy}
                onClick={()=>{
                  if(!window.confirm(
                    'Discard this unsaved invoice?'
                  ))return;

                  setFile(null);
                  setShowUpload(false);
                  setError('');
                }}>
                Cancel
              </button>

            </div>

          </fieldset>

        </form>}

      {historicalInvoices.length>0&&
        <details>
          <summary>
            Earlier approved project versions
            {' '}({historicalInvoices.length})
          </summary>
          {historicalInvoices.map(displayInvoice)}
        </details>}

      <p className="muted">
        Invoice verification records the purchase review.
        It does not authorize vendor payment or certify
        completed installation work.
      </p>

    </>}

  </section>;
}
