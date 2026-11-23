import DraftHistory5697L, { type DraftHistoryResponse5697L } from './DraftHistory5697L';
import { FictionalFinalReceipt5647 } from './FictionalFinalReceipt5647';
import { FictionalInspectionReview5645 } from './FictionalInspectionReview5645';
import FictionalProjectJourney5519 from './FictionalProjectJourney5519';
import FictionalScenarioWorkspace5482 from './FictionalScenarioWorkspace5482';
import MSRRevisionSummary5354 from './MSRRevisionSummary5354';
import { SalesWorkspace5690 } from './SalesWorkspace5690';
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ScopeWorkBuilder, inferPrimaryWorkCategory } from './ScopeWorkBuilder';
import { MaterialsChecklist5333 } from './MaterialsChecklist5333';
import './style.css';
import { SigningReview } from './SigningReview';
import { SyntheticSignerAuthorization5415 } from './SyntheticSignerAuthorization5415';
import { DocusignSetup } from './DocusignSetup';
import { CompletionEnvelopeInspection } from './CompletionEnvelopeInspection';
import { ComptrollerInspectionReview5247 } from './ComptrollerInspectionReview5247';
import { AccountManagement } from './AccountManagement';
import { CustomerManagement } from './CustomerManagement';
import { CustomerSalesHistory5005 } from './CustomerSalesHistory5005';
import { APP_VERSION_LABEL } from './appVersion';
import { BrandedFooter } from './BrandedFooter';
import { ProjectBrowser } from './ProjectBrowser';
import { InspectionDraftWorkflow5189 } from './InspectionDraftWorkflow5189';
import { ProjectStatusDashboard } from './ProjectStatusDashboard';
import { InstallationScheduling } from './InstallationScheduling';
import { CompletionPreflightReview4586 } from './CompletionPreflightReview4586';
import { CustomerPayments4716 } from './CustomerPayments4716';
import { TechnicianAssignments } from './TechnicianAssignments';
import { AuditHistory } from './AuditHistory';
import { ContractorDirectory } from './ContractorDirectory';
import { PayrollWorkspacePreview4325 } from './PayrollWorkspacePreview4325';
import { OperationalWeeklyPayroll5465 } from './OperationalWeeklyPayroll5465';
import type { PayrollRole4325 } from './PayrollWorkspacePreview4325';
import { CorporateFinancialReports5457 } from './CorporateFinancialReports5457';
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
type Customer = {id:string;legal_name:string;billing_address:string;archived:boolean;primary_contact?:{id:string;name:string}|null};
type Line = {description:string;quantity:string};
type Snapshot = {customer:string;contact:string;billing_address:string;project_location:string;scope:string;equipment:EquipmentLine[];materials:Line[];base_price:string;discount:string;tax:string;total_price:string;payment_option:string;payment_terms:string;commercial_notes:string;marketing_promotion?:boolean;financing_type?:string;customer_phone?:string;customer_email?:string;project_city?:string;project_state?:string;project_zip?:string};
type MSR = {source:string|null;created_at:string;created_by_name:string;created_by:string;prepared_by:string;id:string;number:number;status:string;snapshot:Snapshot;edit_sequence:number;revision_reason:string};
type Project = {id:string;code:string;location:string;state:string;customer:string;sales_associate:string;reviewer:string;current_approved:MSR|null;pending:MSR|null};
const FIELD_LABELS = {customer:'Customer name',contact:'Customer Contact',billing_address:'Billing address',project_location:'Installation address',scope:'Scope of work',base_price:'Base price ($)',discount:'Discount ($)',tax:'Tax ($)',total_price:'Total price ($)',payment_terms:'Payment terms',commercial_notes:'Special Customer Arrangements / Notes',customer_phone:'Customer phone',customer_email:'Customer email',project_city:'Installation city',project_state:'Installation state',project_zip:'Installation ZIP'};
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
function completeDraftAddress(data: Snapshot): Snapshot {
  const match = (data.project_location || '').match(
    /^\s*.+?,\s*([^,]+),\s*([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)\s*$/
  );
  if (!match) return data;

  return {
    ...data,
    project_city: data.project_city || match[1].trim(),
    project_state: data.project_state || match[2].toUpperCase(),
    project_zip: data.project_zip || match[3],
  };
}
type MSRStep5696D =
  'customer'|'scope'|'equipment'|'pricing'|'review';

const MSR_STEPS_5696D: {
  id:MSRStep5696D;
  label:string;
}[] = [
  {id:'customer',label:'1. Customer'},
  {id:'scope',label:'2. Scope of Work'},
  {id:'equipment',label:'3. Equipment'},
  {id:'pricing',label:'4. Pricing'},
  {id:'review',label:'5. Review'},
];


function msrGroup5696G(key:string):MSRStep5696D {
  if ([
    'customer','contact','billing_address','project_location',
    'customer_phone','customer_email','project_city',
    'project_state','project_zip'
  ].includes(key)) return 'customer';
  if (key==='scope') return 'scope';
  if (key==='base_price') return 'equipment';
  return 'pricing';
}

function App(){
 const [user,setUser]=useState<Person|null>(null), [ready,setReady]=useState(false), [error,setError]=useState(''), [busy,setBusy]=useState(false);
 const [customers,setCustomers]=useState<Customer[]>([]), [people,setPeople]=useState<Person[]>([]), [projectRefresh,setProjectRefresh]=useState(0), [selected,setSelected]=useState<Project|null>(null);
 const [msrFeedback,setMsrFeedback]=useState('');
 const [msrStep5696D,setMsrStep5696D]=
   useState<MSRStep5696D>('customer');
 const [msrSavedBaseline5696D,setMsrSavedBaseline5696D]=
   useState('');

 const [snapshot,setSnapshot]=useState<Snapshot|null>(null), [reason,setReason]=useState(''), [history,setHistory]=useState<MSR[]>([]);
 const [documents,setDocuments]=useState<PreparedDocument[]>([]);
 const [primaryWorkCategory,setPrimaryWorkCategory]=useState('');
 const [panel,setPanel]=useState<'salesWorkspace'|'projects'|'dashboard'|'installation'|'customer'|'project'|'accounts'|'customers'|'audit'|'completionInspection'|'technicianAssignments'|'contractorDirectory'|'marketingMsrs'|'visibleMsrs' | 'productCatalog' | 'customerPayments'|'salesHistory'|'financialReports'|'payrollPreview'>('projects');
  const [projectCustomerId,setProjectCustomerId]=useState('');

  const [projectStreet5676,setProjectStreet5676]=useState('');
  const [projectCity5676,setProjectCity5676]=useState('');
  const [projectState5676,setProjectState5676]=useState('');
  const [projectZip5676,setProjectZip5676]=useState('');


  const [customerDraftName5669,setCustomerDraftName5669]=useState('');
  const [customerDuplicateReason5669,setCustomerDuplicateReason5669]=useState('');
  const [customerDuplicateResult5669,setCustomerDuplicateResult5669]=useState<{
    name:string;
    possible_customer_match:boolean;
    company_project_match:boolean;
    restricted_projects_exist:boolean;
    visible_projects:{
      id:string;code:string;location:string;state:string
    }[];
    more_visible_projects:boolean;
  }|null>(null);
  const [customerDuplicateChecked5669,setCustomerDuplicateChecked5669]=useState('');
  const [customerDuplicateBusy5669,setCustomerDuplicateBusy5669]=useState(false);
  const [customerDuplicateError5669,setCustomerDuplicateError5669]=useState('');
  const customerDuplicateReady5669 =
    customerDraftName5669.trim().length<2 ||
    (customerDuplicateChecked5669===customerDraftName5669.trim() &&
     !customerDuplicateBusy5669 && !customerDuplicateError5669);
  const customerDuplicateMatch5669 =
    customerDuplicateReady5669 &&
    Boolean(customerDuplicateResult5669?.possible_customer_match);


  const [projectHistory5664,setProjectHistory5664]=useState<
    {id:string;code:string;location:string;state:string}[]
  >([]);
  const [projectHistoryChecked5664,setProjectHistoryChecked5664]=useState('');
  const [projectHistoryLoading5664,setProjectHistoryLoading5664]=useState(false);
  const [projectHistoryError5664,setProjectHistoryError5664]=useState('');

  const [customerPath,setCustomerPath]=useState<'new'|'existing'>('new');
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
 useEffect(()=>{void (async()=>{await csrf();try{const actor=await api<Person>('me/');if(['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(actor.role)){await load();setPanel(actor.role==='SALES_ASSOCIATE'?'salesWorkspace':'projects');}else if(actor.role==='MARKETING'){setPanel('marketingMsrs');}else{setPanel('dashboard');}setUser(actor);}catch{/* A signed-out browser opens the login form. */}finally{setReady(true);}})();},[]);
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

 useEffect(()=>{
   let cancelled=false;
   setProjectHistory5664([]);
   setProjectHistoryChecked5664('');
   setProjectHistoryError5664('');

   if(panel!=='project'||!projectCustomerId){
     setProjectHistoryLoading5664(false);
     return()=>{cancelled=true;};
   }

   setProjectHistoryLoading5664(true);

   void (async()=>{
     try{
       const found: {id:string;code:string;location:string;state:string}[]=[];
       let page=1;
       while(true){
         if(page>50) throw new Error(
           'Customer project history exceeds the review limit.'
         );
         const params=new URLSearchParams({
           customer:projectCustomerId,
           page:String(page)
         });
         const result=await api<{
           next:string|null;
           results:{id:string;code:string;location:string;state:string}[];
         }>(`projects/?${params.toString()}`);

         if(cancelled)return;
         found.push(...result.results);
         if(!result.next)break;
         page++;
       }
       if(!cancelled){
         setProjectHistory5664(found);
         setProjectHistoryChecked5664(projectCustomerId);
       }
     }catch(e){
       if(!cancelled){
         setProjectHistoryError5664((e as Error).message);
       }
     }finally{
       if(!cancelled)setProjectHistoryLoading5664(false);
     }
   })();

   return()=>{cancelled=true;};
 },[panel,projectCustomerId]);


 useEffect(()=>{
   const name=customerDraftName5669.trim();
   let cancelled=false;
   setCustomerDuplicateResult5669(null);
   setCustomerDuplicateChecked5669('');
   setCustomerDuplicateError5669('');

   if(panel!=='customer'||name.length<2){
     setCustomerDuplicateBusy5669(false);
     return()=>{cancelled=true;};
   }

   setCustomerDuplicateBusy5669(true);
   const timer=window.setTimeout(()=>{
     void api<{
       name:string;
       possible_customer_match:boolean;
       company_project_match:boolean;
       restricted_projects_exist:boolean;
       visible_projects:{
         id:string;code:string;location:string;state:string
       }[];
       more_visible_projects:boolean;
     }>('customer-duplicate-lookup/?name='+encodeURIComponent(name))
       .then(result=>{
         if(cancelled)return;
         setCustomerDuplicateResult5669(result);
         setCustomerDuplicateChecked5669(name);
       })
       .catch(e=>{
         if(!cancelled)setCustomerDuplicateError5669((e as Error).message);
       })
       .finally(()=>{
         if(!cancelled)setCustomerDuplicateBusy5669(false);
       });
   },350);

   return()=>{
     cancelled=true;
     window.clearTimeout(timer);
   };
 },[panel,customerDraftName5669]);

 function choose(p:Project){
  setMsrFeedback('');
  setSelected(p);
  const pending = p.pending;
  const customerRecord = customers.find(c => c.id === p.customer);
  const draft = pending?.snapshot;
  const editableDraft = draft && ['DRAFT','REJECTED'].includes(pending!.status)
    ? completeDraftAddress({
        ...draft,
        contact: draft.contact ||
          customerRecord?.primary_contact?.name || '',
      })
    : draft;
  setSnapshot(editableDraft ?? null);
  setMsrSavedBaseline5696D(JSON.stringify(editableDraft ?? null));
  setReason('');
  setHistory([]);
  const first = p.pending?.snapshot.equipment.find(
    line => 'category_of_work' in line
  );
  setPrimaryWorkCategory(
    inferPrimaryWorkCategory(p.pending?.snapshot.scope ?? '') ||
    (first && 'category_of_work' in first
      ? first.category_of_work : '')
  );
}
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
 async function change(action:string){if(!selected?.pending)return;setMsrFeedback('');await api(`msrs/${selected.pending.id}/transition/`,'POST',{action,expected_sequence:selected.pending.edit_sequence,snapshot,reason});await refresh(selected.id);if(action==='edit')setMsrFeedback('Draft saved successfully.');}
 if(!ready)return <main><p>Opening workspace...</p></main>;
 if(!user)return <main className="login"><div className="gecc-login-identity"><strong><span className="gecc-login-line">Green Energy</span><span className="gecc-login-line">Contracting Corporation</span></strong><span>Business Operations &amp; Management System</span></div><h1>Sign in</h1><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{await csrf();await api('dev-login/','POST',Object.fromEntries(f));await csrf();const actor=await api<Person>('me/');if(['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(actor.role)){await load();setPanel(actor.role==='SALES_ASSOCIATE'?'salesWorkspace':'projects');}else if(actor.role==='MARKETING'){setPanel('marketingMsrs');}else{setPanel('dashboard');}setUser(actor);});}}><label>Username<input name="username" autoComplete="username" required/></label><label>Password<input name="password" type="password" autoComplete="current-password" required/></label><button disabled={busy}>Sign in</button></form>{error&&<p role="alert" className="error">{error}</p>}<div className="login-bottom"><div className="login-product-brand">VERIDIAN</div><p className="login-platform-tagline">Integrated Business Platform</p><p className="login-environment">Local Development Environment</p><div className="login-credit-bar"><BrandedFooter versionLabel={APP_VERSION_LABEL} /></div></div></main>;
 const managerCanCorrect=Boolean(
    selected?.pending?.status==='SUBMITTED' &&
    (user.role==='COMPTROLLER' ||
      (user.role==='SALES_MANAGER' &&
       selected.reviewer===user.id))
  );
  const editable=selected?.state!=='CANCELLED' && selected?.pending &&
    (['DRAFT','REJECTED'].includes(selected.pending.status) ||
     managerCanCorrect);
 const approver=['SALES_MANAGER','COMPTROLLER'].includes(user.role);
 const submitPaymentReady = Boolean(
   snapshot?.financing_type &&
   ['50_PERCENT_DEPOSIT', '100_PERCENT_COMPLETION'].includes(
     snapshot.payment_option
   ) &&
   snapshot.payment_terms.trim()
 );
 return <><header><div className="brand">VERIDIAN <span>Business Operations &amp; Management System</span></div><div>{user.username} <span className="badge">{user.role.replaceAll('_',' ')}</span><button className="quiet" onClick={()=>void run(async()=>{await api('logout/','POST',{});setUser(null);setSelected(null);setInstallationFocusId(null);setPanel('projects');})}>Sign out</button></div></header><main>
 <div className="title"><div>{panel==='contractorDirectory'?<p className="eyebrow">VERIDIAN / CONTRACTOR COMPENSATION</p>:panel==='technicianAssignments'||panel==='installation'||panel==='dashboard'?<p className="eyebrow">VERIDIAN / OPERATIONS</p>:null}<h1>{panel==='salesWorkspace'?'Sales Workspace':panel==='payrollPreview'?'Payroll - Design Preview':panel==='financialReports'?'Corporate Financial Reports':panel==='customerPayments'?'Customer Payments':panel==='productCatalog'?'Product Catalog':panel==='contractorDirectory'?'Contractor Directory':panel==='technicianAssignments'?'Technician Assignments':panel==='installation'?'Installation Scheduling':panel==='dashboard'?'Project Status Dashboard':panel==='visibleMsrs'?'Master Sales Records':panel==='salesHistory'?'Sales Opportunity History':'Customers & projects'}</h1></div><div className="actions">{panel!=='contractorDirectory'&&panel!=='visibleMsrs'&&panel!=='productCatalog'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<button className="quiet" onClick={()=>void run(()=>refresh(selected?.id))} disabled={busy}>Refresh</button>}{panel!=='contractorDirectory'&&panel!=='visibleMsrs'&&panel!=='productCatalog'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<><button onClick={()=>setPanel('customer')}>Add customer</button><button disabled={busy} onClick={()=>void run(async()=>{await load();setProjectCustomerId('');setPanel('project');})}>Create project</button></>}</div></div>
 {error&&<div role="alert" className="error">{error}</div>}
   <div className="veridian-navigation-row" style={{display:"flex",flexWrap:"nowrap",overflowX:"auto",gap:"8px",alignItems:"center",whiteSpace:"nowrap",paddingBottom:"6px"}}><button className="quiet" type="button" onClick={()=>setPanel('dashboard')}>Project Status Dashboard</button><button className="quiet" type="button" onClick={()=>setPanel('salesHistory')}>Sales Opportunity History</button><button className="quiet" type="button" onClick={()=>{setInstallationFocusId(null);setPanel('installation');}}>Installation Scheduling</button>{['INSTALLATION_MANAGER','CEO','COMPTROLLER'].includes(user.role)&&<button className="quiet" type="button" onClick={()=>setPanel('technicianAssignments')}>Technician Assignments</button>}{['CEO','COMPTROLLER','SALES_MANAGER','INSTALLATION_MANAGER','SALES_ASSOCIATE','TECHNICIAN'].includes(user.role)&&<button className="quiet" type="button" onClick={()=>setPanel('payrollPreview')}>Payroll (Design Preview)</button>}{user.role==='COMPTROLLER'&&<button className="quiet" type="button" onClick={()=>setPanel('financialReports')}>Corporate Financial Reports</button>}{user.role==='COMPTROLLER'&&<button className="quiet" type="button" onClick={()=>setPanel('customerPayments')}>Customer Payments</button>}{['customers','accounts','audit','completionInspection','installation','technicianAssignments','contractorDirectory','visibleMsrs','productCatalog','salesHistory'].includes(panel)&&<button className="quiet veridian-return-button" type="button" onClick={()=>setPanel('projects')}>Return to Customers &amp; Projects</button>}{['CEO','COMPTROLLER','SALES_MANAGER','INSTALLATION_MANAGER','SALES_ASSOCIATE','TECHNICIAN'].includes(user.role)&&<button className="quiet veridian-secondary-nav-button" type="button" onClick={()=>setPanel('visibleMsrs')}>View Master Sales Records</button>}{panel!=='contractorDirectory'&&panel!=='productCatalog'&&panel!=='salesHistory'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<button className="quiet veridian-secondary-nav-button" onClick={()=>setPanel('customers')}>Manage customers</button>}</div>

   {user.role==='MARKETING'&&<button className="quiet" type="button" onClick={()=>setPanel('marketingMsrs')}>Master Sales Records</button>}

{['SALES_MANAGER','INSTALLATION_MANAGER'].includes(user.role)&&<button className="quiet veridian-secondary-nav-button" type="button" onClick={()=>setPanel('productCatalog')}>Manage Product Catalog</button>}
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
  {panel==='payrollPreview'&&user.role==='COMPTROLLER'&&<FictionalScenarioWorkspace5482 workspace='payroll' />}
{panel==='payrollPreview'&&['CEO','COMPTROLLER','SALES_MANAGER','INSTALLATION_MANAGER','SALES_ASSOCIATE','TECHNICIAN'].includes(user.role)&&<PayrollWorkspacePreview4325 role={user.role as PayrollRole4325} weeklyRegister={user.role==='COMPTROLLER'?<OperationalWeeklyPayroll5465/>:undefined}/>} {panel==='financialReports'&&user.role==='COMPTROLLER'&&<FictionalScenarioWorkspace5482 workspace='financial' />}
{panel==='financialReports'&&user.role==='COMPTROLLER'&&<CorporateFinancialReports5457 api={api}/>} {panel==='marketingMsrs'&&user.role==='MARKETING'&&<MarketingMSRDirectory api={api}/>}
  {panel==='salesHistory'&&<CustomerSalesHistory5005 projectId={selected?.id??''} actorRole={user.role} onRecordStatus={async (id, status, reason) => {await api(`projects/${id}/sales-status/`, 'POST', {sales_status: status, reason});}} />}{panel==='visibleMsrs'&&['CEO','COMPTROLLER','SALES_MANAGER','INSTALLATION_MANAGER','SALES_ASSOCIATE','TECHNICIAN'].includes(user.role)&&<VisibleMSRDirectory api={api}/>}
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

 {panel==='customers'&&['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&<CustomerManagement api={api} onChanged={load} onBack={()=>setPanel('projects')} onCreateProject={id=>{setProjectCustomerId(id);setPanel('project');}}/>}
 {panel!=='contractorDirectory'&&panel!=='salesHistory'&&user.role==='COMPTROLLER'&&<button className="quiet veridian-secondary-nav-button" onClick={()=>setPanel('accounts')}>User management</button>}
 {panel!=='contractorDirectory'&&panel!=='salesHistory'&&user.role==='COMPTROLLER'&&<button className="quiet veridian-secondary-nav-button" onClick={()=>setPanel('audit')}>Audit history</button>}
  {panel!=='contractorDirectory'&&panel!=='salesHistory'&&user.role==='COMPTROLLER'&&<button className="quiet veridian-secondary-nav-button" onClick={()=>setPanel('completionInspection')}>Completion Envelope Inspection</button>}
 {user.role==='COMPTROLLER'&&panel==='audit'&&<AuditHistory api={api} onBack={()=>setPanel('projects')}/>}
  {user.role==='COMPTROLLER'&&panel==='completionInspection'&&<CompletionEnvelopeInspection api={api}/>}
 {user.role==='COMPTROLLER'&&panel==='accounts'&&<AccountManagement actorId={user.id} api={api} onChanged={load} onBack={()=>setPanel('projects')}/>}
 {user.role==='COMPTROLLER'&&!['accounts','customers','audit','dashboard','installation','completionInspection','technicianAssignments','contractorDirectory','visibleMsrs','salesHistory'].includes(panel)&&<DocusignSetup api={api} run={run} busy={busy}/>}
 {panel==='salesWorkspace'&&user.role==='SALES_ASSOCIATE'&&
    <SalesWorkspace5690
      api={api}
      onStartNew={()=>{
        setCustomerPath('new');
        setPanel('customer');
      }}
      onFindProjects={()=>{
        setSelected(null);
        setPanel('projects');
      }}
      onOpenProject={id=>void run(()=>openProjectDetail(id))}
    />}
  {panel==='customer'&&<section><h2>New customer</h2><details className="veridian-customer-instructions"><summary style={{display:"inline-block",cursor:"pointer",padding:"10px 14px",background:"#142B3B",color:"#FFFFFF",borderRadius:"4px",fontWeight:600,marginBottom:"12px"}}>Instructions</summary><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 1 - Enter customer information</strong><p>Enter the customer's legal name and billing address. Add their email and phone number if available. Check the information before saving.</p></div><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 2 - Check for an existing customer</strong><p>Before creating a new customer, select Manage customers and check whether the customer is already listed. Look for the customer's legal name and billing address. If the customer already exists, use that record instead of making another one. If a separate record is needed, explain why in the box labeled Why do you need another customer record?</p></div><p className="muted"><strong>Before leaving this screen:</strong> Select Save customer to save your information or Close to exit without saving.</p></details><fieldset style={{border:"1px solid #D7E3E7",borderRadius:"6px",padding:"14px",marginBottom:"16px"}}><legend style={{fontWeight:700}}>Customer type</legend><div style={{display:"flex",flexDirection:"column",alignItems:"flex-start",gap:"14px"}}><label style={{display:"inline-flex",alignItems:"center",gap:"12px",width:"auto",cursor:"pointer"}}><input type="radio" name="customer_path_105" value="new" style={{width:"18px",height:"18px",flex:"0 0 auto",margin:0}} checked={customerPath==="new"} onChange={()=>setCustomerPath("new")}/><strong style={{fontSize:"1.125rem",whiteSpace:"nowrap"}}>New customer</strong></label><label style={{display:"inline-flex",alignItems:"center",gap:"12px",width:"auto",cursor:"pointer"}}><input type="radio" name="customer_path_105" value="existing" style={{width:"18px",height:"18px",flex:"0 0 auto",margin:0}} checked={customerPath==="existing"} onChange={()=>setCustomerPath("existing")}/><strong style={{fontSize:"1.125rem",whiteSpace:"nowrap"}}>Existing customer with new project</strong></label></div></fieldset>{customerPath==="new"?<form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{const created=await api<Customer>('customers/','POST',Object.fromEntries(f));await load();setProjectCustomerId(created.id);setPanel('project');});}}><div className="grid"><label>Legal name<input name="legal_name" required value={customerDraftName5669} onChange={e=>{setCustomerDraftName5669(e.target.value);setCustomerDuplicateReason5669('');}}/></label>
<div style={{gridColumn:"1 / -1"}}>
  {customerDraftName5669.trim().length>=2&&
   !customerDuplicateReady5669&&
   !customerDuplicateError5669&&
   <p role="status">Checking company customer records...</p>}
  {customerDuplicateError5669&&
   <p role="alert" className="error">
     Customer lookup unavailable: {customerDuplicateError5669}.
     Saving is paused until the check succeeds.
   </p>}
  {customerDuplicateReady5669&&customerDuplicateMatch5669&&
   <div className="veridian-guide-banner veridian-guide-banner--info">
     <strong>Possible existing customer</strong>
     <p>
       A customer with this name already exists in VERIDIAN.
       Check whether this is the same person before creating another record.
     </p>
     {customerDuplicateResult5669?.company_project_match&&
       <p>Projects already exist for a customer with this name.</p>}
     {customerDuplicateResult5669?.visible_projects.map(p=>
       <p key={p.id}>{p.code} - {p.location} ({p.state})</p>
     )}
     {customerDuplicateResult5669?.restricted_projects_exist&&
       <p>Other company projects may be restricted.
          Ask your Sales Manager to review the existing customer.</p>}
     {customerDuplicateResult5669?.more_visible_projects&&
       <p>Additional authorized projects exist.</p>}
     <button type="button" className="quiet"
       onClick={()=>setCustomerPath('existing')}>
       Use existing customer with new project
     </button>
   </div>}
</div>
<label>Billing address<input name="billing_address" required/></label><label>Email<input name="email" type="email"/></label><label>Phone<input name="phone"/></label><details open={customerDuplicateMatch5669} style={{margin:"12px 0"}}><summary style={{cursor:"pointer"}}>Possible duplicate? Explain why another customer record is necessary</summary><label>Reason for a separate customer record<input name="duplicate_reason" value={customerDuplicateReason5669} onChange={e=>setCustomerDuplicateReason5669(e.target.value)}/></label></details></div><button disabled={busy||!customerDuplicateReady5669||(customerDuplicateMatch5669&&!customerDuplicateReason5669.trim())}>Save customer</button><button type="button" className="quiet" onClick={()=>setPanel('projects')}>Close</button></form>:<div><p>Select <strong>Continue to new project</strong> to choose an existing customer. No new customer record will be created.</p><button type="button" disabled={busy} onClick={()=>void run(async()=>{await load();setProjectCustomerId('');setPanel('project');})}>Continue to new project</button><button type="button" className="quiet" onClick={()=>setPanel('projects')}>Close</button></div>}</section>}
 {panel==='project'&&<section><h2>New project</h2><details className="veridian-project-instructions-5678" style={{marginBottom:"16px"}}><summary style={{display:"inline-block",cursor:"pointer",background:"#142B3B",color:"#FFFFFF",padding:"10px 14px",borderRadius:"4px",fontWeight:600}}>Instructions</summary><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 1 - Choose the customer</strong><p>Select the correct customer from the list. If the customer is missing, use Add customer first. Check the customer carefully to avoid duplicate projects.</p></div><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 2 - Enter project details</strong><p>Enter the installation address. Choose the Sales Associate and Sales Manager responsible for this project. If a separate project record is needed for a possible duplicate, explain why in the box labeled Why do you need another project?</p></div><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Step 3 - Create the draft</strong><p>Check your entries, then select Create draft. This starts the project record. It does not mean the Master Sales Record is approved or that the customer has signed a contract.</p></div><p className="muted"><strong>Before leaving this screen:</strong> Select Create draft to save the project as a draft or Close to exit without saving.</p></details><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);void run(async()=>{const p=await api<Project>('projects/','POST',Object.fromEntries(f));await load();setProjectCustomerId('');await openProjectDetail(p.id);});}}><div className="grid"><label>Customer<select aria-label="Customer" name="customer" required value={projectCustomerId} onChange={e=>setProjectCustomerId(e.target.value)}><option value="">Choose customer</option>{customers.filter(c=>!c.archived).map(c=><option key={c.id} value={c.id}>{c.legal_name}</option>)}</select></label>
<label>
  Installation Street Address
  <input
    aria-label="Installation street address"
    required
    maxLength={500}
    value={projectStreet5676}
    onChange={e=>setProjectStreet5676(e.target.value)}
  />
</label>
<label>
  Installation City
  <input
    aria-label="Installation city"
    required
    maxLength={100}
    value={projectCity5676}
    onChange={e=>setProjectCity5676(e.target.value)}
  />
</label>
<label>
  Installation State (2 letters)
  <input
    aria-label="Installation state"
    required
    maxLength={2}
    minLength={2}
    pattern="[A-Za-z]{2}"
    placeholder="MD"
    value={projectState5676}
    onChange={e=>setProjectState5676(
      e.target.value.toUpperCase().replace(/[^A-Z]/g,'')
    )}
  />
</label>
<label>
  Installation ZIP Code
  <input
    aria-label="Installation ZIP code"
    required
    inputMode="numeric"
    pattern="[0-9]{5}(-[0-9]{4})?"
    placeholder="21016"
    value={projectZip5676}
    onChange={e=>setProjectZip5676(e.target.value)}
  />
</label>
<input
  type="hidden"
  name="location"
  value={
    projectStreet5676.trim().replace(/,\s*$/,'')+', '+
    projectCity5676.trim()+', '+
    projectState5676.trim().toUpperCase()+' '+
    projectZip5676.trim()
  }
/>
<label>Sales Associate<select aria-label="Sales Associate" name="sales_associate" required defaultValue={user.role==='SALES_ASSOCIATE'?user.id:''}><option value="">Choose associate</option>{people.filter(p=>p.role==='SALES_ASSOCIATE').map(p=><option key={p.id} value={p.id}>{employeeLabel(p)}</option>)}</select></label><label>Sales Manager<select aria-label="Sales Manager" name="reviewer" required defaultValue={user.role==='SALES_MANAGER'?user.id:''}><option value="">Choose reviewer</option>{people.filter(p=>p.role==='SALES_MANAGER').map(p=><option key={p.id} value={p.id}>{employeeLabel(p)}</option>)}</select></label>
{projectCustomerId&&projectHistoryLoading5664&&
  <p role="status">Checking this customer's existing projects...</p>}
{projectCustomerId&&projectHistoryError5664&&
  <p role="alert" className="error">
    Could not check existing projects: {projectHistoryError5664}
  </p>}
{projectCustomerId&&
 projectHistoryChecked5664===projectCustomerId&&
 !projectHistoryLoading5664&&
 !projectHistoryError5664&&(
   projectHistory5664.length===0?
   <p role="status">No existing projects found for this customer.</p>:
   <div style={{gridColumn:"1 / -1"}}>
     <div className="veridian-guide-banner veridian-guide-banner--info">
       <strong>Existing projects for this customer</strong>
       <ul>
         {projectHistory5664.map(p=>
           <li key={p.id}>
             <strong>{p.code}</strong> - {p.location} ({p.state})
           </li>
         )}
       </ul>
     </div>
     <label>
       Why is another project needed for this customer?
       <input name="duplicate_reason" maxLength={2000}/>
       <small>
         If another project already exists at this installation address,
         explain what makes this a separate job.
       </small>
     </label>
   </div>
 )}
</div><button disabled={busy||projectHistoryLoading5664||Boolean(projectHistoryError5664)||!projectCustomerId||projectHistoryChecked5664!==projectCustomerId}>Create draft</button><button type="button" className="quiet" onClick={()=>setPanel('projects')}>Close</button></form></section>}
 {['SALES_ASSOCIATE','SALES_MANAGER','COMPTROLLER'].includes(user.role)&&!['customer','project','accounts','customers','audit','dashboard','installation','completionInspection','technicianAssignments','contractorDirectory','visibleMsrs','productCatalog','salesHistory','salesWorkspace'].includes(panel)&&<div className="workspace"
      style={user.role==='SALES_ASSOCIATE'&&selected
        ?{gridTemplateColumns:'minmax(0,1fr)'}
        :undefined}>
      {(user.role!=='SALES_ASSOCIATE'||!selected)&&
      <ProjectBrowser<Project> api={api} selectedId={selected?.id} refreshKey={projectRefresh} onChoose={project=>{void run(()=>openProjectDetail(project.id));}}/>}
 <article>
    {user.role==='SALES_ASSOCIATE'&&selected&&
      <button type="button" className="quiet"
        style={{marginBottom:14}}
        onClick={()=>{
          if(snapshot&&
             JSON.stringify(snapshot)!==msrSavedBaseline5696D&&
             !window.confirm(
               'You have unsaved changes. Leave this project?'
             ))return;
          setSelected(null);
          setPanel('projects');
        }}>
        Back to My projects
      </button>}
    {!selected?<section className="empty"><h2>Your commercial workspace</h2><p>Select a project to prepare its Master Sales Record or review an approval.</p></section>:<><section><div className="title"><div><h2>{selected.code}</h2><p className="muted">{selected.location}</p></div><span className="badge" style={{fontSize:"1.25rem",fontWeight:800,padding:"8px 12px"}}>{selected.state}</span></div>
 <details className="veridian-msr-instructions-5686" style={{marginBottom:"16px"}}><summary style={{display:"inline-block",cursor:"pointer",background:"#142B3B",color:"#FFFFFF",padding:"10px 14px",borderRadius:"4px",fontWeight:600}}>Instructions</summary><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Master Sales Record - How to use this screen</strong><p><strong>Step 1 - Complete the record.</strong> Check the customer, work scope, prices, equipment, materials, and financing choice. Financing classification and the customer's payment arrangement are selected separately. A payment exception requires its own documented CEO approval before installation. Approved historical MSRs remain unchanged.</p><p><strong>Step 2 - Save or submit.</strong> Select Save draft to keep editing later. Select Save &amp; submit when the record is ready for review.</p><p><strong>Step 3 - Review and approval.</strong> The assigned Sales Manager or Comptroller can correct a submitted MSR with a reason. Saving creates a new version and preserves the original. A different authorized reviewer must approve the corrected version.</p><p><strong>Step 4 - Protect approved records.</strong> An approved version is locked. To change commercial information, enter a revision reason and create a new version. Use Version history to review earlier records.</p></div></details><div className="versionbar"><span style={{fontSize:"1.125rem",fontWeight:700}}>Approved: {selected.current_approved?`Version ${selected.current_approved.number}.0`:'None yet'}</span><span style={{fontSize:"1.125rem",fontWeight:700}}>Pending: {selected.pending?`Version ${selected.pending.number}.0  -  ${selected.pending.status}`:'None'}</span><button className="quiet" onClick={()=>void run(async()=>setHistory(await api<MSR[]>(`projects/${selected.id}/history/`)))}>Version history</button></div>
 <DraftHistory5697L
   key={selected.id}
   projectId={selected.id}
   load={(id)=>api<DraftHistoryResponse5697L>(
     `projects/${id}/draft-history/`
   )}
 />
 {selected.current_approved&&<details><summary>View approved version {selected.current_approved.number}.0</summary><Summary data={selected.current_approved.snapshot}/></details>}
 {history.map(v=><details key={v.id}>
      <summary>Version {v.number}.0 - {v.status}</summary>
      <MSRRevisionSummary5354
        version={v}
        sourceVersion={history.find(previous=>previous.id===v.source)}
      />
      <Summary data={v.snapshot}/>
    </details>)}
 {selected.pending&&snapshot?<>
<h3>Master Sales Record  -  Version {selected.pending.number}.0</h3>
{user.role==='SALES_ASSOCIATE'&&
  <div style={{
    margin:'16px 0',
    padding:'14px',
    border:'1px solid #D7E3E7',
    borderRadius:8
  }}>
    <div aria-label="Master Sales Record steps"
      style={{
        display:'flex',
        flexWrap:'wrap',
        gap:8,
        marginBottom:14
      }}>
      {MSR_STEPS_5696D.map(step=>
        <button key={step.id} type="button"
          className={msrStep5696D===step.id?'':'quiet'}
          aria-current={msrStep5696D===step.id?'step':undefined}
          onClick={()=>setMsrStep5696D(step.id)}>
          {step.label}
        </button>
      )}
    </div>
    <p style={{margin:'0 0 12px'}}>
      <strong>
        {MSR_STEPS_5696D.find(s=>s.id===msrStep5696D)?.label}
      </strong>
      <span className="muted">
        {' '}? Navigation installed; section grouping is next.
      </span>
    </p>
    <div style={{
      display:'flex',
      gap:12,
      alignItems:'center',
      flexWrap:'wrap'
    }}>
      {editable&&selected.pending.status!=='SUBMITTED'&&
        <button type="button" disabled={busy}
          onClick={()=>void run(()=>change('edit'))}>
          Save draft
        </button>}
      <strong role="status" aria-live="polite">
        {busy?'Processing...':
          snapshot&&
          JSON.stringify(snapshot)!==msrSavedBaseline5696D
            ?'Unsaved changes'
            :'No unsaved changes detected'}
      </strong>
      {msrFeedback&&
        <span style={{color:'#087F75',fontWeight:700}}>
          {msrFeedback}
        </span>}
    </div>
  </div>}
<fieldset disabled={!editable||busy}>
  <div style={{
    display:'flex',
    gap:24,
    flexWrap:'wrap',
    marginBottom:16,
    padding:12,
    border:'1px solid #D7E3E7',
    borderRadius:8
  }}>
    <div>
      <strong>Sales Associate</strong>
      <div>{people.find(p=>p.id===selected.sales_associate)
        ? employeeLabel(people.find(p=>p.id===selected.sales_associate)!)
        : 'Assigned associate unavailable'}</div>
    </div>
    <div>
      <strong>Sales Manager</strong>
      <div>{people.find(p=>p.id===selected.reviewer)
        ? employeeLabel(people.find(p=>p.id===selected.reviewer)!)
        : 'Assigned manager unavailable'}</div>
    </div>
  </div>
  <div className="grid">{(['customer','contact','billing_address','project_location','customer_phone','customer_email','project_city','project_state','project_zip','scope','base_price','discount','tax','total_price','payment_terms','commercial_notes'] as const)
.map(key=><React.Fragment key={key}>
{(user.role!=='SALES_ASSOCIATE'||
  msrGroup5696G(key)===msrStep5696D||
  (key==='base_price'&&msrStep5696D==='pricing'))&&
<>{key==='scope'&&<ScopeWorkBuilder value={snapshot.scope} onChange={value=>{setSnapshot({...snapshot,scope:value});setPrimaryWorkCategory(inferPrimaryWorkCategory(value));}}/>}
{key==='base_price'&&
 (user.role!=='SALES_ASSOCIATE'||msrStep5696D==='equipment')&&
 <div style={{gridColumn:'1 / -1'}}><EquipmentCatalogEditor4534 api={api} primaryCategory={primaryWorkCategory} items={snapshot.equipment} onChange={items=>setSnapshot({...snapshot,equipment:items})}/><MaterialsChecklist5333 items={snapshot.materials} onChange={items=>setSnapshot({...snapshot,materials:items})}/></div>}
{(key!=='base_price'||user.role!=='SALES_ASSOCIATE'||
  msrStep5696D==='pricing')&&
 <label style={key==='scope'?{gridColumn:'1 / -1'}:undefined}>{key==='scope'?'Final Scope of Work - Review before submitting':FIELD_LABELS[key]}{['scope','payment_terms','commercial_notes'].includes(key)?<textarea aria-label={key==='scope'?'Final Scope of Work - Review before submitting':FIELD_LABELS[key]} rows={key==='scope'?8:undefined} style={key==='scope'?{width:'100%',minHeight:'180px',resize:'vertical'}:undefined} value={snapshot[key]??''} onChange={e=>setSnapshot({...snapshot,[key]:e.target.value})}/>:<input aria-label={FIELD_LABELS[key]} value={snapshot[key]??''} onChange={e=>setSnapshot({...snapshot,[key]:e.target.value})}/>}</label>}
{key==='contact'&&
  <div style={{
    gridColumn:'1 / -1',
    display:'flex',
    gap:14,
    alignItems:'center',
    flexWrap:'wrap',
    marginBottom:8
  }}>
    <label style={{
      display:'flex',
      alignItems:'center',
      gap:8,
      width:'auto'
    }}>
      <input
        type="checkbox"
        style={{width:18,height:18,minWidth:18,margin:0}}
        checked={Boolean(snapshot.customer) &&
          snapshot.contact===snapshot.customer}
        onChange={e=>setSnapshot({
          ...snapshot,
          contact:e.target.checked?snapshot.customer:''
        })}
      />
      Same as customer
    </label>
    {customers.find(c=>c.id===selected.customer)?.primary_contact?.name &&
      <button type="button" className="quiet"
        onClick={()=>{
          const contact=customers.find(
            c=>c.id===selected.customer
          )?.primary_contact?.name;
          if(contact)setSnapshot({...snapshot,contact});
        }}>
        Use primary contact
      </button>}
  </div>}
</>}</React.Fragment>)}

{(user.role!=='SALES_ASSOCIATE'||msrStep5696D==='pricing')&&<>
<div style={{gridColumn:'1 / -1',margin:'10px 0 14px'}}>
      <label style={{display:'flex',alignItems:'center',gap:10,width:'auto'}}>
        <input
          type="checkbox"
          aria-label="Marketing Promotion"
          style={{width:18,height:18,minWidth:18,margin:0}}
          checked={snapshot.marketing_promotion===true}
          onChange={event=>setSnapshot({
            ...snapshot,
            marketing_promotion:event.target.checked
          })}
        />
        <strong>Marketing Promotion</strong>
      </label>
      <p className="muted" style={{margin:'5px 0 0'}}>
        Identifies a marketing promotion associated with this project.
        This checkbox does not change the selling price or create a
        customer benefit. Record approved discounts or company-paid
        benefits separately.
      </p>
    </div>
    <label>Financing<select aria-label="Financing" value={snapshot.financing_type??''} onChange={e=>setSnapshot({...snapshot,financing_type:e.target.value})}><option value="">Choose financing</option><option value="NON_FINANCED">Non-financed</option><option value="FINANCED">Financed</option></select></label><label>Payment arrangement
  <select aria-label="Payment arrangement"
    value={snapshot.payment_option}
    onChange={e=>{
      const option=e.target.value;
      const terms=option==='50_PERCENT_DEPOSIT'
        ? '50% deposit due the day before installation; remaining 50% due after installation.'
        : option==='100_PERCENT_COMPLETION'
          ? '100% of the project price due upon completion.'
          : snapshot.payment_option==='OTHER_APPROVAL_REQUIRED'
            ? snapshot.payment_terms : '';
      setSnapshot({...snapshot,payment_option:option,payment_terms:terms});
    }}>
    <option value="">Choose payment arrangement</option>
    <option value="50_PERCENT_DEPOSIT">50% deposit day before installation; balance after installation</option>
    <option value="100_PERCENT_COMPLETION">100% upon completion</option>
    <option value="OTHER_APPROVAL_REQUIRED">Other - Describe proposed terms</option>
  </select>
</label></>}</div></fieldset>{!submitPaymentReady&&editable&&
    (user.role!=='SALES_ASSOCIATE'||
     msrStep5696D==='pricing'||msrStep5696D==='review')&&
    <p role="status" className="muted">
      Choose financing and an agreed payment arrangement. Other terms can be saved in a draft but require a separate approval workflow before submission.
    </p>}

{user.role==='SALES_ASSOCIATE'&&msrStep5696D==='review'&&snapshot&&
 <section style={{padding:18,border:'1px solid #D7E3E7',
                   borderRadius:8,margin:'16px 0'}}>
  <h3>Review your Master Sales Record</h3>
  <p><strong>Customer:</strong> {snapshot.customer}</p>
  <p><strong>Installation:</strong> {snapshot.project_location}</p>
  <p><strong>Scope of Work:</strong></p>
  <p style={{whiteSpace:'pre-wrap'}}>
    {snapshot.scope||'Not entered'}
  </p>
  <p><strong>Equipment lines:</strong> {snapshot.equipment.length}</p>
  <p><strong>Material lines:</strong> {snapshot.materials.length}</p>
  <p><strong>Base price:</strong> ${snapshot.base_price}</p>
  <p><strong>Total price:</strong> ${snapshot.total_price}</p>
  <p><strong>Financing:</strong> {snapshot.financing_type||'Not selected'}</p>
  <p><strong>Payment arrangement:</strong>
    {' '+(snapshot.payment_option||'Not selected')}
  </p>
  <p className="muted">
    Saving a draft does not submit or approve this record.
  </p>
 </section>}
<div className="actions">{editable&&selected.pending.status!=='SUBMITTED'&&<><button disabled={busy} onClick={()=>void run(()=>change('edit'))}>Save draft</button>{(user.role!=='SALES_ASSOCIATE'||
 msrStep5696D==='review')&&<button disabled={busy||!submitPaymentReady} title={!submitPaymentReady?'Choose financing and an authorized payment arrangement before submitting.':undefined} onClick={()=>void run(async()=>{setMsrFeedback('');if(!submitPaymentReady)throw new Error('Choose financing and an authorized payment arrangement before submitting.');await api(`msrs/${selected.pending!.id}/transition/`,'POST',{action:'edit',expected_sequence:selected.pending!.edit_sequence,snapshot});const p=await api<Project>(`projects/${selected.id}/`);choose(p);await api(`msrs/${p.pending!.id}/transition/`,'POST',{action:'submit',expected_sequence:p.pending!.edit_sequence});await refresh(selected.id);setMsrFeedback('Master Sales Record submitted for review. Approval is still required.');})}>Save & submit</button>}</>}{managerCanCorrect&&editable&&
      <button
        disabled={busy||!reason.trim()}
        onClick={()=>void run(async()=>{
          await change('edit');
          setMsrFeedback(
            'Manager correction saved as a new version. The original is preserved. Independent approval is required.'
          );
        })}>
        Save manager correction
      </button>}
    {selected.state!=='CANCELLED'&&selected.pending.status==='SUBMITTED'&&approver&&<>
      <button
        disabled={busy||
          selected.pending.prepared_by===user.id||
          selected.pending.created_by===user.id}
        title={
          selected.pending.prepared_by===user.id||
          selected.pending.created_by===user.id
            ? 'A different authorized reviewer must approve this record.'
            : undefined
        }
        onClick={()=>void run(()=>change('approve'))}>
        Approve version
      </button><button disabled={busy||!reason.trim()||selected.pending.prepared_by===user.id||selected.pending.created_by===user.id} className="quiet" onClick={()=>void run(()=>change('reject'))}>Reject with reason</button></>}</div></>:<p className="muted">The approved record is locked. Create a revision to change any commercial field.</p>}{msrFeedback&&<p role="status" aria-live="polite" style={{color:"#087F75",fontWeight:700}}>{msrFeedback}</p>}{error&&<p role="alert" className="error">{error}</p>}
 <label>Review note / revision reason<textarea aria-label="Review note / revision reason" value={reason} onChange={e=>setReason(e.target.value)}/></label>{selected.state!=='CANCELLED'&&selected.current_approved&&!selected.pending&&<button disabled={busy||!reason.trim()} onClick={()=>void run(async()=>{await api(`projects/${selected.id}/revision/`,'POST',{reason,expected_approved_id:selected.current_approved!.id});await refresh(selected.id);})}>Create revision</button>}
 {selected.code==='104-SA-2026-11-22' && <FictionalProjectJourney5519 key={`${selected.id}-${selected.current_approved?.id ?? 'pending'}`} projectId={selected.id}
    onOpenInstallation={() => {
      setInstallationFocusId(selected.id);
      setEvidenceProjectId(selected.id);
      setPanel('installation');
    }}
    onOpenPayments={user.role === 'COMPTROLLER'
      ? () => {
          setEvidenceProjectId(selected.id);
          setInstallationFocusId(selected.id);
          setPanel('customerPayments');
        }
      : undefined} approved={Boolean(selected.current_approved)} projectState={selected.state} completionVisible={Boolean(approver && selected.current_approved)} />}<div id="journey-documents-5519" className="documents"><h3>Documents</h3><InspectionDraftWorkflow5189 api={api} projectId={selected.id} actorRole={user.role}/><ApprovedMSRSource4530 api={api} projectId={selected.id}/><FictionalDocumentPreviews4525/><div className="veridian-guide-banner veridian-guide-banner--info"><strong>Contracts and Invoices - Preparation Guide</strong><p><strong>Step 1 - Check approval.</strong> A contract or invoice can be prepared after the Master Sales Record is approved.</p><p><strong>Step 2 - Prepare the documents.</strong> Select Prepare contract or Prepare invoice. Each action creates an unsigned preparation copy.</p><p><strong>Step 3 - Review the PDFs.</strong> Download each prepared document. Check the customer information, work details, pricing, and payment terms before proceeding.</p><p><strong>Step 4 - Review signing.</strong> Use the Signing review section to check who will sign and in what order. For contracts and invoices, the customer signs first. Preparing or downloading a PDF does not mean it has been sent or signed. Electronic sending is not yet enabled.</p></div><p className="muted">Prepare unsigned interactive PDFs from the current approved MSR. Completion certificates are preparation copies; work completion and signature dates stay blank.</p>{selected.current_approved&&approver&&selected.state!=='CANCELLED'&&<div className="actions">{['CONTRACT','INVOICE',...(selected.current_approved.snapshot.financing_type==='FINANCED'?['COMPLETION_FINANCED']:selected.current_approved.snapshot.financing_type==='NON_FINANCED'?['COMPLETION_NON_FINANCED']:[])].map(kind=><button className="quiet" disabled={busy} key={kind} onClick={()=>void run(async()=>{await api(`msrs/${selected.current_approved!.id}/documents/`,'POST',{kind});setDocuments(await api<PreparedDocument[]>(`projects/${selected.id}/documents/`));})}>{kind==='CONTRACT'?'Prepare contract':kind==='INVOICE'?'Prepare invoice':'Prepare completion certificate'}</button>)}</div>}{!selected.current_approved&&<p className="muted">Document preparation becomes available after approval.</p>}{documents.map(doc=><div key={doc.id} className="document-row"><div><strong>{doc.kind.replaceAll('_',' ')}</strong><span>MSR {doc.msr_version}.0 - Unsigned preparation copy - Renderer {doc.renderer_version}</span><span>Prepared {new Date(doc.created_at).toLocaleString('en-US',{dateStyle:'medium',timeStyle:'short',timeZone:'America/New_York'})} ET</span></div><a href={doc.download_url}>Download PDF</a></div>)}</div>
 {approver && selected.current_approved &&
    <section className="documents">
      <h3 id="journey-completion-5519">Project Completion Review</h3>
      {user.role === 'COMPTROLLER' &&
       selected.id === '5e02a9d2-1028-41ea-a3bd-624116ef3b0b' && (
         <FictionalInspectionReview5645 />
       )}
      {user.role === 'COMPTROLLER' &&
       selected.id === '5e02a9d2-1028-41ea-a3bd-624116ef3b0b' && (
         <FictionalFinalReceipt5647 />
       )}
      {user.role === 'COMPTROLLER' && (
        <ComptrollerInspectionReview5247
          key={`${selected.id}-${selected.current_approved.id}`}
          api={api}
          projectId={selected.id}
        />
      )}
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
        actorRole={user.role}
      />
      <p className="muted">
        The exact final Receipt PDF, authenticated evidence of its email
        delivery, and the correctly matched, provider-verified completed
        DocuSign Completion Certificate are mandatory.
        The Customer Satisfaction Survey is optional.
      </p>
    </section>}
  {selected.code==='104-SA-2026-11-22'&&selected.current_approved&&selected.state!=='CANCELLED'&&
  <SyntheticSignerAuthorization5415
    key={`${selected.id}-${selected.current_approved.id}-synthetic`}
    projectId={selected.id}
    actorRole={user.role}
    busy={busy}
    api={api}
    run={run}
  />}
<div id="journey-signing-5519"><SigningReview key={`${selected.id}-${selected.current_approved?.id}`} projectId={selected.id} msrId={selected.current_approved?.id} actorRole={user.role} workflowIntent={workflowIntent} finance={selected.current_approved?.snapshot.financing_type} active={selected.state!=='CANCELLED'} approver={approver} comptroller={user.role==='COMPTROLLER'} actorId={user.id} busy={busy} api={api} run={run}/></div>
 {approver&&<button className="quiet" disabled={busy||!reason.trim()} onClick={()=>void run(async()=>{await api(`projects/${selected.id}/state/`,'POST',{action:selected.state==='CANCELLED'?'reopen':'cancel',reason,expected_state:selected.state});await refresh(selected.id);})}>{selected.state==='CANCELLED'?'Reopen project':'Cancel project'}</button>}
 </section></>}</article></div>}<BrandedFooter versionLabel={APP_VERSION_LABEL} /></main></>;
}
function Lines({title,items,onChange}:{title:string;items:Line[];onChange:(items:Line[])=>void}){return <div><h3>{title}</h3>{items.map((item,i)=><div className="line" key={i}><label>Description<input value={item.description} onChange={e=>onChange(items.map((x,n)=>n===i?{...x,description:e.target.value}:x))}/></label><label>Quantity<input value={item.quantity} onChange={e=>onChange(items.map((x,n)=>n===i?{...x,quantity:e.target.value}:x))}/></label><button type="button" className="quiet" onClick={()=>onChange(items.filter((_,n)=>n!==i))}>Remove</button></div>)}<button type="button" className="quiet" onClick={()=>onChange([...items,{description:'',quantity:'1'}])}>Add {title.toLowerCase()} item</button></div>;}
function Summary({data}:{data:Snapshot}){return <dl>{Object.entries(data).map(([k,v])=><React.Fragment key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{Array.isArray(v)?v.map(x=>`${x.description}  -  ${x.quantity}`).join('; ')||'None':v}</dd></React.Fragment>)}</dl>;}
createRoot(document.getElementById('root')!).render(<App/>);
