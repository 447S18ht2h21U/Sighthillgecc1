import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { SigningReview } from './SigningReview';
import { DocusignSetup } from './DocusignSetup';
import { CompletionEnvelopeInspection } from './CompletionEnvelopeInspection';
import { AccountManagement } from './AccountManagement';
import { CustomerManagement } from './CustomerManagement';
import { APP_VERSION_LABEL } from './appVersion';
import { BrandedFooter } from './BrandedFooter';
import { ProjectBrowser } from './ProjectBrowser';
import { ProjectStatusDashboard } from './ProjectStatusDashboard';
import { InstallationScheduling } from './InstallationScheduling';
import { CompletionPreflightReview4586 } from './CompletionPreflightReview4586';
import { CustomerPayments4716 } from './CustomerPayments4716';
import { TechnicianAssignments } from './TechnicianAssignments';
import { AuditHistory } from './AuditHistory';
import { ContractorDirectory } from './ContractorDirectory';
import { MarketingMSRDirectory } from './MarketingMSRDirectory';
import { VisibleMSRDirectory } from './VisibleMSRDirectory';
import { FictionalDocumentPreviews4525 } from './FictionalDocumentPreviews4525';
import { ApprovedMSRSource4530 } from './ApprovedMSRSource4530';
import { EquipmentCatalogEditor4534 } from './EquipmentCatalogEditor4534';
import { NamedProductCatalog4547 } from './NamedProductCatalog4547';
import type { EquipmentLine } from './EquipmentCatalogEditor4534';
type Person = {id:string;username:string;role:string;first_name?:string;last_name?:string};
function employeeLabel(person: Person): string {
  const fullName = [person.first_name, person.last_name]
    .filter(Boolean).join(' ').trim();
  return fullName ? `${fullName} (${person.username})` : person.username;
}
type Customer = {id:string;legal_name:string;billing_address:string;archived:boolean};
type Line = {description:string;quantity:string};
type Snapshot = {customer:string;contact:string;billing_address:string;project_location:string;scope:string;equipment:EquipmentLine[];materials:Line[];base_price:string;discount:string;tax:string;total_price:string;payment_option:string;payment_terms:string;commercial_notes:string;financing_type?:string;customer_phone?:string;customer_email?:string;project_city?:string;project_state?:string;project_zip?:string};
type MSR = {id:string;number:number;status:string;snapshot:Snapshot;edit_sequence:number;revision_reason:string};
type Project = {id:string;code:string;location:string;state:string;current_approved:MSR|null;pending:MSR|null};
const FIELD_LABELS = {customer:'Customer name',contact:'Contact',billing_address:'Billing address',project_location:'Installation address',scope:'Scope of work',base_price:'Base price ($)',discount:'Discount ($)',tax:'Tax ($)',total_price:'Total price ($)',payment_terms:'Payment terms',commercial_notes:'Commercial notes',customer_phone:'Customer phone',customer_email:'Customer email',project_city:'Installation city',project_state:'Installation state',project_zip:'Installation ZIP'};
type PreparedDocument = {id:string;kind:string;msr_version:number;filename:string;download_url:string;status:string;created_at:string;renderer_version:string};
let token = '';
async function csrf(){ token = (await (await fetch('/api/csrf/')).json()).csrfToken; }
async function api<T>(path:string, method='GET', data?:unknown):Promise<T>{
  const response = await fetch(`/api/${path}`,{method,headers:{'Content-Type':'application/json','X-CSRFToken':token},body:data===undefined?undefined:JSON.stringify(data)});
  const contentType = response.headers.get('content-type') || '';
  const unexpectedResponse =
    'The server returned an unexpected response. ' +
    'Check the current records before trying again. ' +
    `HTTP status: ${response.status}.`;

  if (!contentType.toLowerCase().includes('application/json')) {
    throw new Error(unexpectedResponse);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error(unexpectedResponse);
  }

  if (!response.ok) {
    if (body === null || typeof body !== 'object' || Array.isArray(body)) {
      throw new Error(unexpectedResponse);
    }

    const details = Object.entries(body)
      .map(([key, value]) =>
        `${key.replaceAll('_', ' ')}: ${
          typeof value === 'string' ? value : JSON.stringify(value)
        }`
      )
      .join(' ');

    throw new Error(details || unexpectedResponse);
  }

  return body as T;
}
function App(){
 const [user,setUser]=useState<Person|null>(null), [ready,setReady]=useState(false), [error,setError]=useState(''), [busy,setBusy]=useState(false);
 const [customers,setCustomers]=useState<Customer[]>([]), [people,setPeople]=useState<Person[]>([]), [projectRefresh,setProjectRefresh]=useState(0), [selected,setSelected]=useState<Project|null>(null);
 const [snapshot,setSnapshot]=useState<Snapshot|null>(null), [reason,setReason]=useState(''), [history,setHistory]=useState<MSR[]>([]);
 const [documents,setDocuments]=useState<PreparedDocument[]>([]);
 const [panel,setPanel]=useState<'projects'|'dashboard'|'installation'|'customer'|'project'|'accounts'|'customers'|'audit'|'completionInspection'|'technicianAssignments'|'contractorDirectory'|'marketingMsrs'|'visibleMsrs' | 'productCatalog' | 'customerPayments'>('projects');
  const [projectCustomerId,setProjectCustomerId]=useState('');
  const [workflowIntent,setWorkflowIntent]=useState<'none'|'completion'>('none');
  const [installationFocusId,setInstallationFocusId]=useState<string | null>(null);
  const [evidenceProjectId,setEvidenceProjectId]=useState('');
 async function run(job:()=>Promise<void>){setBusy(true);setError('');try{await job();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function load(){
  const c:Customer[]=[];
  // Read every authorized active-customer page so project creation is not limited to the first 50.
  let page=1;
  while(true){const batch=await api<{results:Customer[];next:string|null}>(`customers/?status=ACTIVE&page=${page}`);c.push(...batch.results);if(!batch.next)break;page++;}
  const d=await api<Person[]>('directory/');
  setCustomers(c);setPeople(d);setProjectRefresh(n=>n+1);
 }
 useEffect(()=>{void (async()=>{await csrf();try{const actor=await api<Person>('me/');if(['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(actor.role)){await load();setPanel('projects');}else if(actor.role==='MARKETING'){setPanel('marketingMsrs');}else{setPanel('dashboard');}setUser(actor);}catch{/* A signed-out browser opens the login form. */}finally{setReady(true);}})();},[]);
 useEffect(()=>{
  if(!user)return;
  let last=0;
  const ping=()=>{if(Date.now()-last>60000){last=Date.now();void api('activity/','POST',{}).catch(()=>{setError('Your session expired. Sign in again.');setUser(null);});}};
  window.addEventListener('pointerdown',ping);window.addEventListener('keydown',ping);
  return()=>{window.removeEventListener('pointerdown',ping);window.removeEventListener('keydown',ping);};
 },[user]);
 useEffect(()=>{
  let cancelled=false;setDocuments([]);
  if(selected?.id&&user&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role))void api<PreparedDocument[]>(`projects/${selected.id}/documents/`).then(d=>{if(!cancelled)setDocuments(d);}).catch(e=>{if(!cancelled)setError((e as Error).message);});
  return()=>{cancelled=true;};
 },[selected?.id,user?.id]);
 function choose(p:Project){setSelected(p);setSnapshot(p.pending?.snapshot??null);setReason('');setHistory([]);}
  function reviewDashboardInstallation(id:string) {
    setInstallationFocusId(id);
    setPanel('installation');
  }
 async function refresh(id?:string){await load();if(id){const p=await api<Project>(`projects/${id}/`);choose(p);}}
  // Always open the complete, current project from Django.
  // List rows are for browsing, not the MSR editing source of truth.
  async function openProjectDetail(id:string) {
    const project = await api<Project>(`projects/${id}/`);
    choose(project);
    setPanel('projects');
  }
  async function openDashboardProject(id:string) {
    if (!user || !['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)) return;
    await run(() => openProjectDetail(id));
  }
 async function change(action:string){if(!selected?.pending)return;await api(`msrs/${selected.pending.id}/transition/`,'POST',{action,expected_sequence:selected.pending.edit_sequence,snapshot,reason});await refresh(selected.id);}
 if(!ready)return <main><p>Opening workspace...</p></main>;
 if(!user)return <main className="login"><div className="gecc-login-identity"><strong><span className="gecc-login-line">Green Energy</span><span className="gecc-login-line">Contracting Corporation</span></strong><span>Business Operations &amp; Management System</span></div><h1>Sign in</h1><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{await csrf();await api('dev-login/','POST',Object.fromEntries(f));await csrf();const actor=await api<Person>('me/');if(['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(actor.role)){await load();setPanel('projects');}else if(actor.role==='MARKETING'){setPanel('marketingMsrs');}else{setPanel('dashboard');}setUser(actor);});}}><label>Username<input name="username" autoComplete="username" required/></label><label>Password<input name="password" type="password" autoComplete="current-password" required/></label><button disabled={busy}>Sign in</button></form>{error&&<p role="alert" className="error">{error}</p>}<div className="login-bottom"><div className="login-product-brand">VERIDIAN</div><p className="login-platform-tagline">Integrated Business Platform</p><p className="login-environment">Local Development Environment</p><div className="login-credit-bar"><BrandedFooter versionLabel={APP_VERSION_LABEL} /></div></div></main>;
 const editable=selected?.state!=='CANCELLED' && selected?.pending && ['DRAFT','REJECTED'].includes(selected.pending.status);
 const approver=['SALES_MANAGER','COMPTROLLER'].includes(user.role);
 const requiredPaymentOption =
   snapshot?.financing_type === 'FINANCED'
     ? '50_PERCENT_DEPOSIT'
     : snapshot?.financing_type === 'NON_FINANCED'
       ? '100_PERCENT_COMPLETION'
       : null;
 const paymentMismatch = Boolean(
   requiredPaymentOption && snapshot &&
   snapshot.payment_option !== requiredPaymentOption
 );
  const submitPaymentReady = Boolean(
    snapshot?.financing_type &&
    requiredPaymentOption &&
    snapshot?.payment_option === requiredPaymentOption
  );
 return <><header><div className="brand">VERIDIAN <span>Business Operations &amp; Management System</span></div><div>{user.username} <span className="badge">{user.role.replaceAll('_',' ')}</span><button className="quiet" onClick={()=>void run(async()=>{await api('logout/','POST',{});setUser(null);setSelected(null);setInstallationFocusId(null);setPanel('projects');})}>Sign out</button></div></header><main>
 <div className="title"><div>{panel==='contractorDirectory'?<p className="eyebrow">VERIDIAN / CONTRACTOR COMPENSATION</p>:panel==='technicianAssignments'||panel==='installation'||panel==='dashboard'?<p className="eyebrow">VERIDIAN / OPERATIONS</p>:null}<h1>{panel==='customerPayments'?'Customer Payments':panel==='productCatalog'?'Product Catalog':panel==='contractorDirectory'?'Contractor Directory':panel==='technicianAssignments'?'Technician Assignments':panel==='installation'?'Installation Scheduling':panel==='dashboard'?'Project Status Dashboard':panel==='visibleMsrs'?'Master Sales Records':'Customers & projects'}</h1></div><div className="actions">{panel!=='contractorDirectory'&&panel!=='visibleMsrs'&&panel!=='productCatalog'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<button className="quiet" onClick={()=>void run(()=>refresh(selected?.id))} disabled={busy}>Refresh</button>}{panel!=='contractorDirectory'&&panel!=='visibleMsrs'&&panel!=='productCatalog'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<><button onClick={()=>setPanel('customer')}>Add customer</button><button disabled={busy} onClick={()=>void run(async()=>{await load();setProjectCustomerId('');setPanel('project');})}>Create project</button></>}</div></div>
 {error&&<div role="alert" className="error">{error}</div>}
   <div className="veridian-navigation-row"><button className="quiet" type="button" onClick={()=>setPanel('dashboard')}>Project Status Dashboard</button><button className="quiet" type="button" onClick={()=>{setInstallationFocusId(null);setPanel('installation');}}>Installation Scheduling</button>{['INSTALLATION_MANAGER','CEO','COMPTROLLER'].includes(user.role)&&<button className="quiet" type="button" onClick={()=>setPanel('technicianAssignments')}>Technician Assignments</button>}{['CEO','COMPTROLLER'].includes(user.role)&&<button className="quiet" type="button" onClick={()=>setPanel('contractorDirectory')}>Contractor Compensation</button>}{user.role==='COMPTROLLER'&&<button className="quiet" type="button" onClick={()=>setPanel('customerPayments')}>Customer Payments</button>}{['customers','accounts','audit','completionInspection','installation','technicianAssignments','contractorDirectory','visibleMsrs','productCatalog'].includes(panel)&&<button className="quiet veridian-return-button" type="button" onClick={()=>setPanel('projects')}>Return to Customers &amp; Projects</button>}</div>
    
   {user.role==='MARKETING'&&<button className="quiet" type="button" onClick={()=>setPanel('marketingMsrs')}>Master Sales Records</button>}
  {['CEO','COMPTROLLER','SALES_MANAGER','INSTALLATION_MANAGER','SALES_ASSOCIATE','TECHNICIAN'].includes(user.role)&&<button className="quiet" type="button" onClick={()=>setPanel('visibleMsrs')}>View Master Sales Records</button>}
{['SALES_MANAGER','INSTALLATION_MANAGER'].includes(user.role)&&<button className="quiet" type="button" onClick={()=>setPanel('productCatalog')}>Manage Product Catalog</button>}
  {panel==='productCatalog'&&['SALES_MANAGER','INSTALLATION_MANAGER'].includes(user.role)&&<NamedProductCatalog4547 api={api}/>}
  {panel==='customerPayments'&&user.role==='COMPTROLLER'&&
    <div className="installation-evidence-nav-actions">
      <button type="button" className="quiet"
        onClick={() => {
          setInstallationFocusId(evidenceProjectId || null);
          setPanel('installation');
        }}>
        Return to Installation Scheduling
      </button>
    </div>}
    {panel==='customerPayments'&&user.role==='COMPTROLLER'&&<CustomerPayments4716 api={api} selectedProjectId={evidenceProjectId} onBack={()=>setPanel('projects')}/>}
  {panel==='marketingMsrs'&&user.role==='MARKETING'&&<MarketingMSRDirectory api={api}/>}
  {panel==='visibleMsrs'&&['CEO','COMPTROLLER','SALES_MANAGER','INSTALLATION_MANAGER','SALES_ASSOCIATE','TECHNICIAN'].includes(user.role)&&<VisibleMSRDirectory api={api}/>}
{panel==='dashboard'&&<ProjectStatusDashboard onOpenProject={['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role) ? openDashboardProject : undefined} onReviewInstallation={reviewDashboardInstallation} onBack={()=>setPanel(['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)?'projects':'installation')} backLabel={['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)?'Back to Customers & Projects':'Back to Installation Scheduling'}/>}
  {panel==='technicianAssignments'&&['INSTALLATION_MANAGER','CEO','COMPTROLLER'].includes(user.role)&&<TechnicianAssignments api={api}/>}
  {panel==='contractorDirectory'&&['CEO','COMPTROLLER'].includes(user.role)&&<ContractorDirectory api={api} onBack={()=>setPanel(user.role==='CEO'?'dashboard':'projects')} returnLabel={user.role==='CEO'?'Return to Project Status Dashboard':'Return to Customers & Projects'}/>}
 {panel==='installation'&&user.role==='COMPTROLLER'&&
    <section className="installation-evidence-navigation">
      <h3>Resolve Installation Readiness Evidence</h3>
      <p>
        Review outstanding payment or cancellation evidence using
        the existing authorized workspaces. Navigation does not
        verify evidence or authorize installation.
      </p>
      <div className="installation-evidence-nav-actions">
        <button type="button"
          disabled={busy || !evidenceProjectId} onClick={() => setPanel('customerPayments')}>
          Review Customer Payments
        </button>
        <button type="button" className="veridian-project-evidence-button"
          disabled={busy || !evidenceProjectId}
          onClick={() => {
            const projectId = evidenceProjectId;
            void run(async () => {
              await openProjectDetail(projectId);
              setWorkflowIntent('none');
              setPanel('projects');
            });
          }}>
          Review Selected Project Evidence
        </button>
      </div>
      <p className="muted">
        First select the project under Schedule an installation. Then use Review Selected Project Evidence. For cancellation evidence, review the approved project in
        Customers &amp; Projects. Open Signing review and then
        Project verification evidence. Verify the correct MSR version
        before recording any attestation.
      </p>
    </section>}
    {panel==='installation'&&<InstallationScheduling
    api={api}
    actorId={user.id}
    actorRole={user.role}
    selectedProjectId={installationFocusId ?? undefined}
    onProjectSelected={(id) => {
      setInstallationFocusId(null);
      setEvidenceProjectId(id);
      if (!['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)) return;
      void run(async () => {
        const project = await api<Project>(`projects/${id}/`);
        choose(project);
      });
    }}
    onReturnToProject={() => {
      setInstallationFocusId(null);
      setWorkflowIntent('completion');
      setPanel('projects');
    }}
/>} 
 {panel!=='contractorDirectory'&&panel!=='productCatalog'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<button className="quiet" onClick={()=>setPanel('customers')}>Manage customers</button>}
 {panel==='customers'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<CustomerManagement api={api} onChanged={load} onBack={()=>setPanel('projects')} onCreateProject={id=>{setProjectCustomerId(id);setPanel('project');}}/>}
 {panel!=='contractorDirectory'&&user.role==='COMPTROLLER'&&<button className="quiet" onClick={()=>setPanel('accounts')}>User management</button>}
 {panel!=='contractorDirectory'&&user.role==='COMPTROLLER'&&<button className="quiet" onClick={()=>setPanel('audit')}>Audit history</button>}
  {panel!=='contractorDirectory'&&user.role==='COMPTROLLER'&&<button className="quiet" onClick={()=>setPanel('completionInspection')}>Completion Envelope Inspection</button>}
 {user.role==='COMPTROLLER'&&panel==='audit'&&<AuditHistory api={api} onBack={()=>setPanel('projects')}/>}
  {user.role==='COMPTROLLER'&&panel==='completionInspection'&&<CompletionEnvelopeInspection api={api}/>}
 {user.role==='COMPTROLLER'&&panel==='accounts'&&<AccountManagement actorId={user.id} api={api} onChanged={load} onBack={()=>setPanel('projects')}/>}
 {user.role==='COMPTROLLER'&&!['accounts','customers','audit','dashboard','installation','completionInspection','technicianAssignments','contractorDirectory','visibleMsrs'].includes(panel)&&<DocusignSetup api={api} run={run} busy={busy}/>}
 {panel==='customer'&&<section><h2>New customer</h2><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 1 - Enter customer information</strong><p>Enter the customer's legal name and billing address. Add their email and phone number if available. Check the information before saving.</p></div><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 2 - Check for an existing customer</strong><p>Before creating a new customer, select Manage customers and check whether the customer is already listed. Look for the customer's legal name and billing address. If the customer already exists, use that record instead of making another one. If a separate record is needed, explain why in the box labeled Why do you need another customer record?</p></div><p className="muted"><strong>Before leaving this screen:</strong> Select Save customer to save your information or Close to exit without saving.</p><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{const created=await api<Customer>('customers/','POST',Object.fromEntries(f));await load();setProjectCustomerId(created.id);setPanel('project');});}}><div className="grid"><label>Legal name<input name="legal_name" required/></label><label>Billing address<input name="billing_address" required/></label><label>Email<input name="email" type="email"/></label><label>Phone<input name="phone"/></label><label>Why do you need another customer record? (If needed)<input name="duplicate_reason"/><small>If this customer is already listed, VERIDIAN may ask why you need another record. Explain why here. If you are not sure, ask your Sales Manager.</small></label></div><button disabled={busy}>Save customer</button><button type="button" className="quiet" onClick={()=>setPanel('projects')}>Close</button></form></section>}
 {panel==='project'&&<section><h2>New project</h2><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 1 - Choose the customer</strong><p>Select the correct customer from the list. If the customer is missing, use Add customer first. Check the customer carefully to avoid duplicate projects.</p></div><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 2 - Enter project details</strong><p>Enter the installation address. Choose the Sales Associate and Sales Manager responsible for this project. If a separate project record is needed for a possible duplicate, explain why in the box labeled Why do you need another project?</p></div><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 3 - Create the draft</strong><p>Check your entries, then select Create draft. This starts the project record. It does not mean the Master Sales Record is approved or that the customer has signed a contract.</p></div><p className="muted"><strong>Before leaving this screen:</strong> Select Create draft to save the project as a draft or Close to exit without saving.</p><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{const p=await api<Project>('projects/','POST',Object.fromEntries(f));await load();setProjectCustomerId('');await openProjectDetail(p.id);});}}><div className="grid"><label>Customer<select key={projectCustomerId||'new-project'} aria-label="Customer" name="customer" required defaultValue={projectCustomerId}><option value="">Choose customer</option>{customers.filter(c=>!c.archived).map(c=><option key={c.id} value={c.id}>{c.legal_name}</option>)}</select></label><label>Installation address<input name="location" required/></label><label>Sales Associate<select aria-label="Sales Associate" name="sales_associate" required defaultValue={user.role==='SALES_ASSOCIATE'?user.id:''}><option value="">Choose associate</option>{people.filter(p=>p.role==='SALES_ASSOCIATE').map(p=><option key={p.id} value={p.id}>{employeeLabel(p)}</option>)}</select></label><label>Sales Manager<select aria-label="Sales Manager" name="reviewer" required defaultValue={user.role==='SALES_MANAGER'?user.id:''}><option value="">Choose reviewer</option>{people.filter(p=>p.role==='SALES_MANAGER').map(p=><option key={p.id} value={p.id}>{employeeLabel(p)}</option>)}</select></label><label>Why do you need another project? (If needed)<input name="duplicate_reason"/><small>A customer can have more than one job at the same address. If another project already exists there, explain what makes this job different. Example: The first job is for solar panels. This job is for battery storage. If you are changing work in an existing contract, ask your Sales Manager before creating another project.</small></label></div><button disabled={busy}>Create draft</button><button type="button" className="quiet" onClick={()=>setPanel('projects')}>Close</button></form></section>}
 {['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&!['customer','project','accounts','customers','audit','dashboard','installation','completionInspection','technicianAssignments','contractorDirectory','visibleMsrs','productCatalog'].includes(panel)&&<div className="workspace"><ProjectBrowser<Project> api={api} selectedId={selected?.id} refreshKey={projectRefresh} onChoose={project=>{void run(()=>openProjectDetail(project.id));}}/>
 <article>{!selected?<section className="empty"><h2>Your commercial workspace</h2><p>Select a project to prepare its Master Sales Record or review an approval.</p></section>:<><section><div className="title"><div><h2>{selected.code}</h2><p className="muted">{selected.location}</p></div><span className="badge">{selected.state}</span></div>
 <div className="veridian-guide-banner veridian-guide-banner--info"><strong>Master Sales Record - How to use this screen</strong><p><strong>Step 1 - Complete the record.</strong> Check the customer, work scope, prices, equipment, materials, and financing choice. The financing classification controls the payment option: financed projects use a 50% deposit and 50% at completion; non-financed projects use 100% at completion. A payment exception requires its own documented CEO approval before installation. Approved historical MSRs remain unchanged.</p><p><strong>Step 2 - Save or submit.</strong> Select Save draft to keep editing later. Select Save &amp; submit when the record is ready for review.</p><p><strong>Step 3 - Review and approval.</strong> An authorized reviewer can approve a submitted version or reject it with a reason. A rejected version can be corrected and submitted again.</p><p><strong>Step 4 - Protect approved records.</strong> An approved version is locked. To change commercial information, enter a revision reason and create a new version. Use Version history to review earlier records.</p></div><div className="versionbar"><span>Approved: {selected.current_approved?`Version ${selected.current_approved.number}.0`:'None yet'}</span><span>Pending: {selected.pending?`Version ${selected.pending.number}.0  -  ${selected.pending.status}`:'None'}</span><button className="quiet" onClick={()=>void run(async()=>setHistory(await api<MSR[]>(`projects/${selected.id}/history/`)))}>Version history</button></div>
 {selected.current_approved&&<details><summary>View approved version {selected.current_approved.number}.0</summary><Summary data={selected.current_approved.snapshot}/></details>}
 {history.map(v=><details key={v.id}><summary>Version {v.number}.0  -  {v.status}</summary><p>{v.revision_reason}</p><Summary data={v.snapshot}/></details>)}
 {selected.pending&&snapshot?<><h3>Master Sales Record  -  Version {selected.pending.number}.0</h3><fieldset disabled={!editable||busy}><div className="grid">{(['customer','contact','billing_address','project_location','scope','base_price','discount','tax','total_price','payment_terms','commercial_notes','customer_phone','customer_email','project_city','project_state','project_zip'] as const).map(key=><label key={key}>{FIELD_LABELS[key]}{['scope','payment_terms','commercial_notes'].includes(key)?<textarea aria-label={FIELD_LABELS[key]} value={snapshot[key]??''} onChange={e=>setSnapshot({...snapshot,[key]:e.target.value})}/>:<input aria-label={FIELD_LABELS[key]} value={snapshot[key]??''} onChange={e=>setSnapshot({...snapshot,[key]:e.target.value})}/>}</label>)}<label>Financing<select aria-label="Financing" value={snapshot.financing_type??''} onChange={e=>{const finance=e.target.value;setSnapshot({...snapshot,financing_type:finance,payment_option:finance==='FINANCED'?'50_PERCENT_DEPOSIT':finance==='NON_FINANCED'?'100_PERCENT_COMPLETION':snapshot.payment_option});}}><option value="">Choose financing</option><option value="NON_FINANCED">Non-financed</option><option value="FINANCED">Financed</option></select></label><label>Payment option (set by financing)<input aria-label="Payment option (set by financing)" readOnly value={snapshot.payment_option==='50_PERCENT_DEPOSIT'?'50% deposit / 50% at completion':snapshot.payment_option==='100_PERCENT_COMPLETION'?'100% at completion':'Not established'}/></label></div><EquipmentCatalogEditor4534 api={api} items={snapshot.equipment} onChange={items=>setSnapshot({...snapshot,equipment:items})}/><Lines title="Materials" items={snapshot.materials} onChange={items=>setSnapshot({...snapshot,materials:items})}/></fieldset>{paymentMismatch&&<div role="alert" className="veridian-guide-banner veridian-guide-banner--info"><strong>Payment schedule needs review.</strong><p>This draft's saved payment option does not match its financing classification. Approved historical MSRs will not be changed automatically.</p>{editable&&snapshot&&requiredPaymentOption&&<button type="button" className="quiet" disabled={busy} onClick={()=>setSnapshot({...snapshot,payment_option:requiredPaymentOption})}>Use required payment option in this draft</button>}</div>}{!submitPaymentReady&&editable&&
    <p role="status" className="muted">
      To submit the MSR, choose financing and confirm the required
      payment option. You can still save your draft.
    </p>}
    <p className="muted">Before installation, verify the customer's signed Contract, the applicable cancellation deadline, and the five-calendar-day waiting period measured from the verified Contract signature. Confirm the required deposit has cleared and been bank-verified, or that a valid CEO-approved project-specific payment exception applies. The customer Invoice signature is not a pre-installation requirement. Physical equipment serial numbers must also be recorded before installation, unless an authorized unit-specific exception applies.</p><div className="actions">{editable&&<><button disabled={busy} onClick={()=>void run(()=>change('edit'))}>Save draft</button><button disabled={busy||!submitPaymentReady} title={!submitPaymentReady?'Choose financing and its required payment option before submitting.':undefined} onClick={()=>void run(async()=>{if(!submitPaymentReady)throw new Error('Choose financing and the required payment option before submitting.');await api(`msrs/${selected.pending!.id}/transition/`,'POST',{action:'edit',expected_sequence:selected.pending!.edit_sequence,snapshot});const p=await api<Project>(`projects/${selected.id}/`);choose(p);await api(`msrs/${p.pending!.id}/transition/`,'POST',{action:'submit',expected_sequence:p.pending!.edit_sequence});await refresh(selected.id);})}>Save & submit</button></>}{selected.state!=='CANCELLED'&&selected.pending.status==='SUBMITTED'&&approver&&<><button disabled={busy} onClick={()=>void run(()=>change('approve'))}>Approve version</button><button disabled={busy||!reason.trim()} className="quiet" onClick={()=>void run(()=>change('reject'))}>Reject with reason</button></>}</div></>:<p className="muted">The approved record is locked. Create a revision to change any commercial field.</p>}
 <label>Review note / revision reason<textarea aria-label="Review note / revision reason" value={reason} onChange={e=>setReason(e.target.value)}/></label>{selected.state!=='CANCELLED'&&selected.current_approved&&!selected.pending&&<button disabled={busy||!reason.trim()} onClick={()=>void run(async()=>{await api(`projects/${selected.id}/revision/`,'POST',{reason,expected_approved_id:selected.current_approved!.id});await refresh(selected.id);})}>Create revision</button>}
 <div className="documents"><h3>Documents</h3><ApprovedMSRSource4530 api={api} projectId={selected.id}/><FictionalDocumentPreviews4525/><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Contracts and Invoices - Preparation Guide</strong><p><strong>Step 1 - Check approval.</strong> A contract or invoice can be prepared after the Master Sales Record is approved.</p><p><strong>Step 2 - Prepare the documents.</strong> Select Prepare contract or Prepare invoice. Each action creates an unsigned preparation copy.</p><p><strong>Step 3 - Review the PDFs.</strong> Download each prepared document. Check the customer information, work details, pricing, and payment terms before proceeding.</p><p><strong>Step 4 - Review signing.</strong> Use the Signing review section to check who will sign and in what order. For contracts and invoices, the customer signs first. Preparing or downloading a PDF does not mean it has been sent or signed. Electronic sending is not yet enabled.</p></div><p className="muted">Prepare unsigned interactive PDFs from the current approved MSR. Completion certificates are preparation copies; work completion and signature dates stay blank.</p>{selected.current_approved&&approver&&selected.state!=='CANCELLED'&&<div className="actions">{['CONTRACT','INVOICE',...(selected.current_approved.snapshot.financing_type==='FINANCED'?['COMPLETION_FINANCED']:selected.current_approved.snapshot.financing_type==='NON_FINANCED'?['COMPLETION_NON_FINANCED']:[])].map(kind=><button className="quiet" disabled={busy} key={kind} onClick={()=>void run(async()=>{await api(`msrs/${selected.current_approved!.id}/documents/`,'POST',{kind});setDocuments(await api<PreparedDocument[]>(`projects/${selected.id}/documents/`));})}>{kind==='CONTRACT'?'Prepare contract':kind==='INVOICE'?'Prepare invoice':'Prepare completion certificate'}</button>)}</div>}{!selected.current_approved&&<p className="muted">Document preparation becomes available after approval.</p>}{documents.map(doc=><div key={doc.id} className="document-row"><div><strong>{doc.kind.replaceAll('_',' ')}</strong><span>MSR {doc.msr_version}.0 - Unsigned preparation copy - Renderer {doc.renderer_version}</span><span>Prepared {new Date(doc.created_at).toLocaleString('en-US',{dateStyle:'medium',timeStyle:'short',timeZone:'America/New_York'})} ET</span></div><a href={doc.download_url}>Download PDF</a></div>)}</div>
 {approver && selected.current_approved &&
    <section className="documents">
      <h3>Project Completion Review</h3>
      <p className="muted">
        Read-only administrative completion assessment for the selected
        approved project. Operational installation completion is not
        administrative project completion. Candidate documents, local
        email observations, and unverified signing attempts do not
        establish verified evidence or authorize completion.
      </p>
      <CompletionPreflightReview4586
        key={`${selected.id}-${selected.current_approved.id}`}
        projectId={selected.id}
        projectCode={selected.code}
      />
      <p className="muted">
        The exact final Receipt PDF, authenticated evidence of its email
        delivery, and the correctly matched, provider-verified completed
        DocuSign Completion Certificate are mandatory.
        The Customer Satisfaction Survey is optional.
      </p>
    </section>}
  <SigningReview key={`${selected.id}-${selected.current_approved?.id}`} projectId={selected.id} msrId={selected.current_approved?.id} workflowIntent={workflowIntent} finance={selected.current_approved?.snapshot.financing_type} active={selected.state!=='CANCELLED'} approver={approver} comptroller={user.role==='COMPTROLLER'} actorId={user.id} busy={busy} api={api} run={run}/>
 {approver&&<button className="quiet" disabled={busy||!reason.trim()} onClick={()=>void run(async()=>{await api(`projects/${selected.id}/state/`,'POST',{action:selected.state==='CANCELLED'?'reopen':'cancel',reason,expected_state:selected.state});await refresh(selected.id);})}>{selected.state==='CANCELLED'?'Reopen project':'Cancel project'}</button>}
 </section></>}</article></div>}<BrandedFooter versionLabel={APP_VERSION_LABEL} /></main></>;
}
function Lines({title,items,onChange}:{title:string;items:Line[];onChange:(items:Line[])=>void}){return <div><h3>{title}</h3>{items.map((item,i)=><div className="line" key={i}><label>Description<input value={item.description} onChange={e=>onChange(items.map((x,n)=>n===i?{...x,description:e.target.value}:x))}/></label><label>Quantity<input value={item.quantity} onChange={e=>onChange(items.map((x,n)=>n===i?{...x,quantity:e.target.value}:x))}/></label><button type="button" className="quiet" onClick={()=>onChange(items.filter((_,n)=>n!==i))}>Remove</button></div>)}<button type="button" className="quiet" onClick={()=>onChange([...items,{description:'',quantity:'1'}])}>Add {title.toLowerCase()} item</button></div>;}
function Summary({data}:{data:Snapshot}){return <dl>{Object.entries(data).map(([k,v])=><React.Fragment key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{Array.isArray(v)?v.map(x=>`${x.description}  -  ${x.quantity}`).join('; ')||'None':v}</dd></React.Fragment>)}</dl>;}
createRoot(document.getElementById('root')!).render(<App/>);
