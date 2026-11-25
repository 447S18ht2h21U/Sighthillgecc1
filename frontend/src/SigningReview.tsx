import { useEffect, useState } from 'react';
import { VerificationEvidence, ReleaseReview } from './ReleaseReview';
import { SandboxPackage } from './SandboxPackage';
const LICENSE_STATES = "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(' ');
type AdultEvidence = {recorded:boolean;synthetic?:boolean;synthetic_available?:boolean;evidence_id?:string;employee_id?:string;state_of_issue?:string;approved_msr_id?:string;timestamp?:string};
type Signer ={id:string;name:string;email:string;role:string};
type Plan = {id:string;group:string;review:{msr_version:number;customer:{name:string;email:string};gecc:{name:string;email:string;role:string};substitute_reason:string;envelope_preview:{recipients:{signers:{routingOrder:string;name:string;email:string}[]}}};release:{status:string;release_blockers:string[]}};
type API = <T>(path:string, method?:string, data?:unknown)=>Promise<T>;
export function SigningReview({projectId,msrId,actorRole,finance,workflowIntent,active,approver,comptroller,actorId,busy,api,run}:{projectId:string;msrId?:string;actorRole:string;finance?:string;workflowIntent?:'none'|'completion';active:boolean;approver:boolean;comptroller:boolean;actorId:string;busy:boolean;api:API;run:(job:()=>Promise<void>)=>Promise<void>}){
 const [adultEvidence,setAdultEvidence]=useState<AdultEvidence>({recorded:false});
 const [adultState,setAdultState]=useState('');
 const [adultConfirmed,setAdultConfirmed]=useState(false);
 const [adultError,setAdultError]=useState('');
 const [saveError,setSaveError]=useState('');
 const [authorityConfirmed,setAuthorityConfirmed]=useState(false);
 const [customerName,setCustomerName]=useState('');
 const [customerEmail,setCustomerEmail]=useState('');
 const [geccSigner,setGeccSigner]=useState('');
 useEffect(()=>{
  setCustomerName('');
  setCustomerEmail('');
  setGeccSigner('');
  setAuthorityConfirmed(false);
  setSaveError('');
 },[projectId,msrId]);
 const [plans,setPlans]=useState<Plan[]>([]),[signers,setSigners]=useState<Signer[]>([]),[group,setGroup]=useState(workflowIntent==='completion' && finance ? `COMPLETION_${finance}` : 'COMMERCIAL'),[loadError,setLoadError]=useState('');
 useEffect(()=>{let cancelled=false;setPlans([]);setLoadError('');api<Plan[]>(`projects/${projectId}/signing-reviews/`).then(p=>{if(!cancelled)setPlans(p);}).catch(e=>{if(!cancelled)setLoadError(e.message);});return()=>{cancelled=true;};},[projectId,msrId,active,api]);
 useEffect(()=>{let cancelled=false;setSigners([]);if(approver)api<Signer[]>(`projects/${projectId}/signing-candidates/?group=${group}`).then(p=>{if(!cancelled)setSigners(p);}).catch(e=>{if(!cancelled)setLoadError(e.message);});return()=>{cancelled=true;};},[projectId,group,approver,api]);
 useEffect(()=>{
  let cancelled=false;
  setAdultEvidence({recorded:false});
  setAdultState('');
  setAdultConfirmed(false);
  setAdultError('');
  if(msrId && active){
   api<AdultEvidence>(`projects/${projectId}/adult-verification/`)
    .then(result=>{if(!cancelled)setAdultEvidence(result);})
    .catch(error=>{if(!cancelled)setAdultError(String(error.message || error));});
  }
  return()=>{cancelled=true;};
 },[projectId,msrId,active,api]);
 return <div className="documents"><h3>Signing review</h3><p className="muted">Review recipients and routing before connecting Docusign. Unsigned requests expire 75 calendar days after first send. Completed signatures do not expire.</p>{loadError&&<p role="alert" className="error">{loadError}</p>}
 {msrId&&active&&approver&&<VerificationEvidence msrId={msrId} comptroller={comptroller} busy={busy} api={api} run={run}/>}
 {msrId&&active&&<section className="veridian-guide-banner veridian-guide-banner--info">
 <strong>Adult Customer Verification - In-person sale</strong>
 {adultError&&<p role="alert">{adultError}</p>}
 {adultEvidence.recorded
  ? <p role="status">{adultEvidence.synthetic ? 'SYNTHETIC TEST EVIDENCE ? no actual ID inspection. ' : 'Recorded for this approved MSR. '}State of issue: {adultEvidence.state_of_issue}. Employee: {adultEvidence.employee_id}. Recorded: {adultEvidence.timestamp ? new Date(adultEvidence.timestamp).toLocaleString() : 'Timestamp unavailable'}. No license number stored.</p>
  : actorRole==='SALES_ASSOCIATE'
   ? adultEvidence.synthetic_available
    ? <div>
      <p>This is the fictional browser-acceptance project. No physical ID was checked. The record will be permanently labeled SYNTHETIC TEST EVIDENCE.</p>
      <button disabled={busy} onClick={()=>void run(async()=>{const result=await api<AdultEvidence>(`projects/${projectId}/adult-verification/`,'POST',{synthetic:true});setAdultEvidence(result);})}>Record synthetic test evidence</button>
      </div>
    : <form onSubmit={e=>{e.preventDefault();if(!adultConfirmed || !LICENSE_STATES.includes(adultState))return;void run(async()=>{const result=await api<AdultEvidence>(`projects/${projectId}/adult-verification/`,'POST',{state_of_issue:adultState,adult_confirmed:true});setAdultEvidence(result);});}}>
     <p>Confirm the customer is at least 18 after personally checking government-issued photo ID. Do not enter or retain its number or photograph.</p>
     <label>State of Issue<select value={adultState} onChange={e=>setAdultState(e.target.value)} required><option value="">Choose state</option>{LICENSE_STATES.map(s=><option key={s} value={s}>{s}</option>)}</select></label>
     <label style={{display:'flex',alignItems:'center',gap:'0.5rem'}}><input type="checkbox" checked={adultConfirmed} onChange={e=>setAdultConfirmed(e.target.checked)} required style={{width:'auto',margin:0,flex:'0 0 auto'}} /><span>I personally inspected government-issued photo ID and confirmed the customer is at least 18.</span></label>
     <button disabled={busy || !adultConfirmed || !adultState}>Record adult verification</button>
     </form>
   : <p>Awaiting the assigned Sales Associate's in-person adult-identification confirmation. Managers cannot record this check on their behalf.</p>}
 <p className="muted">This verifies an adult-ID review only. Customer signing authority and DocuSign evidence remain separate requirements.</p>
 </section>}
 {msrId&&active&&approver&&<form key={`${projectId}-${msrId}-${group}`} onSubmit={e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget));
if(group==='COMMERCIAL' && (!adultEvidence.recorded || !adultEvidence.evidence_id || !authorityConfirmed)) return;
data.authority_note=adultEvidence.recorded
 ? (adultEvidence.synthetic ? 'SYNTHETIC TEST EVIDENCE reference: ' : 'Assigned Sales Associate adult-ID attestation reference: ') + adultEvidence.evidence_id +
   '. Customer signing authority is recorded separately from adult verification.'
 : 'Customer signing authority requires separate independent approval; no in-person adult attestation asserted.';
setSaveError('');
 void run(async()=>{
  try {
   await api(`msrs/${msrId}/signing-reviews/`,'POST',{
    ...data,group,
    customer_authority_confirmed:group==='COMMERCIAL' && authorityConfirmed
   });
  } catch(error) {
   const message=error instanceof Error ? error.message : String(error);
   setSaveError(message.includes('Exactly one approved, non-revoked customer-signer authorization is required')
    ? 'The customer signing authority confirmation is missing or needs correction.'
    : message);
   return;
  }
  try {
   setPlans(await api<Plan[]>(`projects/${projectId}/signing-reviews/`));
  } catch {
   setSaveError('Signing review was saved, but the list could not be refreshed. Reopen the project before trying again.');
  }
 });}}><div className="grid">
 <label>Signing workflow<select aria-label="Signing workflow" value={group} onChange={e=>{setGroup(e.target.value);setLoadError('');setSaveError('');setGeccSigner('');setAuthorityConfirmed(false);}}><option value="COMMERCIAL">Contract and invoice — customer first</option>{finance&&<option value={`COMPLETION_${finance}`}>Completion certificate — GECC first</option>}</select></label>
 <label>Customer signer full name<input name="customer_name" maxLength={250} value={customerName} onChange={e=>setCustomerName(e.target.value)} required/></label><label>Customer signer email<input name="customer_email" type="email" maxLength={254} value={customerEmail} onChange={e=>setCustomerEmail(e.target.value)} required/></label>
 <label>GECC signer<select name="gecc_signer" aria-label="GECC signer" required value={geccSigner} onChange={e=>setGeccSigner(e.target.value)}><option value="">Choose signer</option>{signers.filter(s=>s.name).map(s=><option key={s.id} value={s.id}>{s.name} · {s.role.replaceAll('_',' ')}</option>)}</select></label>

 {group!=='COMMERCIAL'&&<label>Installation Manager unavailable — substitute reason<textarea name="substitute_reason" maxLength={2000} placeholder="Required when the Comptroller signs in place of the Installation Manager."/></label>}
 </div>
 {group==='COMMERCIAL'&&<label style={{display:'flex',alignItems:'center',gap:'0.5rem',marginTop:'1rem'}}>
  <input type="checkbox" checked={authorityConfirmed} onChange={e=>setAuthorityConfirmed(e.target.checked)} required style={{width:'auto',margin:0,flex:'0 0 auto'}}/>
  <span>{adultEvidence.synthetic
   ? 'Confirm fictional customer signing authority for this software test only.'
   : 'For this ordinary residential sale, the customer has confirmed that they have authority to sign the Contract.'}</span>
 </label>}
 <p className="muted">Prepare the workflow's PDFs first. GECC signer accounts need a full name and email.{group!=='COMMERCIAL'&&' Work completion must be verified before release.'}</p>{saveError&&<p role="alert" className="error">{saveError}</p>}<button disabled={busy || (group==='COMMERCIAL' && (!adultEvidence.recorded || !authorityConfirmed))}>Save signing review</button></form>}
 {plans.map(plan=><details key={plan.id} className="signing-review"><summary>MSR {plan.review.msr_version}.0 · {plan.group.replaceAll('_',' ')} · {plan.release.status.replaceAll('_',' ')}</summary><ol>{[...plan.review.envelope_preview.recipients.signers].sort((a,b)=>Number(a.routingOrder)-Number(b.routingOrder)).map(s=><li key={s.routingOrder}>{s.name} — {s.email}</li>)}</ol>{plan.review.substitute_reason&&<p>GECC substitute reason: {plan.review.substitute_reason}</p>}<p>Release checks</p><ul>{plan.release.release_blockers.map(b=><li key={b}>{b}</li>)}</ul><p className="muted" role="status">Operational sending is not available yet. This signing review does not authorize customer signatures. Complete the required authentic signing evidence and independent release controls before installation. The separate sandbox signing test is for fictional software acceptance only.</p>{approver&&<ReleaseReview actorRole={actorRole} comptroller={comptroller} planId={plan.id} current={plan.release.status==='PREPARED'} actorId={actorId} busy={busy} api={api} run={run}/>}
 {approver&&<SandboxPackage planId={plan.id} current={plan.release.status==='PREPARED'} comptroller={comptroller} busy={busy} api={api} run={run}/>}</details>)}
 </div>;
}
