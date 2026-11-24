import { useEffect, useState } from 'react';
import { SigningTest } from './SigningTest';
type API = <T>(path:string,method?:string,data?:unknown)=>Promise<T>;
type Run = (job:()=>Promise<void>)=>Promise<void>;
type Evidence={id:string;kind:string;data:{verified:boolean;deadline?:string;completion_date?:string;source_reference:string}};
export function VerificationEvidence({msrId,comptroller,busy,api,run}:{msrId:string;comptroller:boolean;busy:boolean;api:API;run:Run}){
 const [rows,setRows]=useState<Evidence[]>([]),[kind,setKind]=useState('CANCELLATION_DEADLINE'),[verified,setVerified]=useState(true),[error,setError]=useState('');const path=`msrs/${msrId}/verification-evidence/`;
 useEffect(()=>{let closed=false;api<Evidence[]>(path).then(r=>{if(!closed)setRows(r);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[path,api]);
 return <details className="verification-evidence"><summary>Project verification evidence</summary><p>Manual verification records are bound to this approved MSR. The app records your attestation; it does not independently verify the referenced evidence. Sending remains disabled.</p>{error&&<p role="alert" className="error">{error}</p>}
 <button type="button" className="quiet" disabled={busy} onClick={()=>void run(async()=>setRows(await api<Evidence[]>(path)))}>Refresh verification evidence</button>
 <ul>{rows.map(r=><li key={r.id}>{r.kind.replaceAll('_',' ')} · {r.data.verified?'Recorded verification':'Withdrawn'} · {r.data.deadline||r.data.completion_date||''} · {r.data.source_reference}</li>)}</ul>
 {comptroller&&<form key={kind} onSubmit={e=>{e.preventDefault();const fields=Object.fromEntries(new FormData(e.currentTarget));const data:{[key:string]:unknown}={...fields,kind,verified};for(const k of ['notice_and_applicability_checked','work_verified','permits_inspections_checked','exceptions_resolved'])data[k]=fields[k]==='on';void run(async()=>{await api(path,'POST',data);setRows(await api<Evidence[]>(path));});}}><div className="grid"><label>Evidence type<select value={kind} onChange={e=>setKind(e.target.value)}><option value="CANCELLATION_DEADLINE">Cancellation deadline</option><option value="WORK_COMPLETION">Work completion</option></select></label><label>Evidence reference<input name="source_reference" maxLength={2000} required/></label><label>Verification note<textarea name="verification_note" maxLength={2000} required/></label></div>
 <label className="sandbox-confirm"><input type="checkbox" checked={verified} onChange={e=>setVerified(e.target.checked)}/>Record verification (clear to withdraw the previous verification)</label>
 {verified&&(kind==='CANCELLATION_DEADLINE'?<><label>Exact cancellation deadline with UTC offset<input name="deadline" placeholder="YYYY-MM-DDTHH:MM:SS-04:00" required/></label><label className="sandbox-confirm"><input type="checkbox" name="notice_and_applicability_checked" required/>I reviewed applicable cancellation rights, notice delivery and the exact deadline against the evidence reference.</label></>:<><label>Verified work-completion date<input type="date" name="completion_date" required/></label><label>Installation Manager unavailable — verification substitute reason<textarea name="substitute_reason" required/></label>{[['work_verified','I verified the approved scope of work is complete.'],['permits_inspections_checked','I reviewed applicable permits and inspections.'],['exceptions_resolved','I verified outstanding exceptions are resolved.']].map(([name,text])=><label className="sandbox-confirm" key={name}><input type="checkbox" name={name} required/>{text}</label>)}</>)}<p>The Comptroller records completion verification as an authorized substitute in this slice; direct Installation Manager operational access is still pending.</p><button disabled={busy}>Save verification evidence</button></form>}
 </details>;
}
const packageDate = new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York',year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'});
type Package={id:string;created_at:string;created_by:string;release:{status:string;blockers:string[]};documents:{kind:string;download_url:string}[];decisions:{decision:string;note:string}[]};

type CommercialTransactionStatus = {
  sandbox_only: boolean;
  send_available: boolean;
  operational_signature_verified: boolean;
  installation_authorized: boolean;
  attempt: null | {
    id: string;
    state: string;
    envelope_id: string | null;
    send_started: boolean;
    can_read_existing: boolean;
    can_resend: boolean;
    provider_observation: null | {
      provider_status: string | null;
      observed_at: string | null;
    };
    retained_documents: {
      kind: string;
      document_id: string;
      pdf_sha256: string;
    }[];
  };
};

function CommercialSigningStatus({
  packageId,
  api,
  busy,
  run,
}: {
  packageId: string;
  api: API;
  busy: boolean;
  run: Run;
}) {
  const [status, setStatus] = useState<CommercialTransactionStatus | null>(null);
  const [error, setError] = useState("");

  const refresh = async () => {
    try {
      const result = await api<CommercialTransactionStatus>(
        `release-packages/${packageId}/commercial-signing/`
      );
      setStatus(result);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  };

  return (
    <div className="sandbox-package">
      <h4>Commercial signing transaction</h4>
      <p>
        Review the existing Contract and Invoice signing transaction.
        This panel cannot create or send a DocuSign envelope.
      </p>

      <button
        type="button"
        className="quiet"
        disabled={busy}
        onClick={() => void run(refresh)}
      >
        Refresh commercial signing status
      </button>

      {error && <p role="alert">{error}</p>}

      {!status && !error && (
        <p>No transaction status has been loaded.</p>
      )}

      {status && (
        <div>
          <p>
            Evidence classification:{" "}
            <strong>
              {status.sandbox_only ? "Fictional sandbox only" : "Unverified"}
            </strong>
          </p>

          {!status.attempt ? (
            <p>
              No commercial signing attempt has been recorded
              for this release package.
            </p>
          ) : (
            <>
              <p>
                Transaction state:{" "}
                <strong>{status.attempt.state.replaceAll("_", " ")}</strong>
              </p>
              <p>
                DocuSign envelope:{" "}
                <strong>
                  {status.attempt.envelope_id || "Not yet recorded"}
                </strong>
              </p>
              <p>
                Latest provider verification:{" "}
                <strong>
                  {status.attempt.provider_observation?.provider_status
                    || "Not yet recorded"}
                </strong>
              </p>
              <p>
                Retained signed documents:{" "}
                <strong>{status.attempt.retained_documents.length}</strong>
              </p>
              {status.attempt.can_read_existing && (
                <p>
                  Existing envelope available for a separately
                  authorized read-only provider check.
                </p>
              )}
              {!status.attempt.can_resend && (
                <p>Automatic resending is prohibited.</p>
              )}
            </>
          )}

          <p>
            Operational signatures:{" "}
            <strong>
              {status.operational_signature_verified
                ? "Verified"
                : "Not verified"}
            </strong>
            . Installation authorization:{" "}
            <strong>
              {status.installation_authorized
                ? "Granted"
                : "Not granted"}
            </strong>.
          </p>

          <p>
            Commercial sending: <strong>Disabled</strong>.
          </p>
        </div>
      )}
    </div>
  );
}


type CommercialSendStatus5610 = {
  sandbox_only:boolean;
  release:{status:string};
  attempt:null|{id:string;state:string;envelope_id:string|null};
};


type CommercialReadResponse5623 = {
  sandbox_only:boolean;
  attempt:null|{
    id:string;
    state:string;
    envelope_id:string|null;
    can_read_existing:boolean;
    provider_observation?:{
      provider_status?:string;
      observed_at?:string;
    }|null;
    retained_documents?:Array<{
      kind:string;
      pdf_sha256:string;
    }>;
  };
};

function CommercialRead5623({
  packageId,api,busy,run
}:{
  packageId:string;api:API;busy:boolean;run:Run;
}){
  const [status,setStatus]=useState<CommercialReadResponse5623|null>(null);
  const [error,setError]=useState('');
  const [confirmed,setConfirmed]=useState(false);
  const [working,setWorking]=useState(false);

  const path=`release-packages/${packageId}/commercial-signing/`;

  async function refresh(){
    const result=await api<CommercialReadResponse5623>(path);
    setStatus(result);
    setError('');
  }

  useEffect(()=>{
    let cancelled=false;
    setStatus(null);
    setConfirmed(false);
    api<CommercialReadResponse5623>(path)
      .then(result=>{
        if(!cancelled)setStatus(result);
      })
      .catch(cause=>{
        if(!cancelled)setError(
          cause instanceof Error?cause.message:String(cause)
        );
      });
    return ()=>{cancelled=true;};
  },[path,api]);

  const attempt=status?.attempt;
  if(!attempt)return null;

  const canRead=status?.sandbox_only===true
    &&attempt.can_read_existing===true
    &&Boolean(attempt.envelope_id);

  async function connectRead(){
    if(!canRead||!confirmed||working||busy||!attempt?.envelope_id)return;
    const expectedAttemptId=attempt.id;
    const expectedEnvelopeId=attempt.envelope_id;
    setWorking(true);
    try{
      await run(async()=>{
        const latest=await api<CommercialReadResponse5623>(path);
        setStatus(latest);

        if(
          latest.sandbox_only!==true
          ||latest.attempt?.id!==expectedAttemptId
          ||latest.attempt?.envelope_id!==expectedEnvelopeId
          ||latest.attempt?.can_read_existing!==true
        ){
          throw new Error(
            'Existing envelope changed. Stop; do not initiate another request.'
          );
        }

        const result=await api<{
          authorization_url:string;
          operation:string;
          environment:string;
          envelope_sent:boolean;
        }>(
          `commercial-signing-attempts/${expectedAttemptId}/connect-read/`,
          'POST',
          {confirmed:true}
        );

        if(
          result.operation!=='READ_ONLY'
          ||result.environment!=='SANDBOX'
          ||result.envelope_sent!==false
        ){
          throw new Error('Unexpected provider-read authorization response.');
        }

        const destination=new URL(result.authorization_url);
        if(
          destination.protocol!=='https:'
          ||!(
            destination.hostname==='docusign.com'
            ||destination.hostname.endsWith('.docusign.com')
            ||destination.hostname==='docusign.net'
            ||destination.hostname.endsWith('.docusign.net')
          )
        ){
          throw new Error('Unexpected DocuSign authorization destination.');
        }

        window.location.assign(destination.href);
      });
    }catch(cause){
      setError(cause instanceof Error?cause.message:String(cause));
    }finally{
      setWorking(false);
    }
  }

  return <section className="sandbox-package">
    <h4>Verify existing DocuSign envelope</h4>
    <p>This is a read-only provider verification of the
      already-sent fictional Contract and Invoice.
      It cannot create or resend an envelope.</p>
    {error&&<p role="alert">{error}</p>}
    <p>Envelope: <strong>{attempt.envelope_id}</strong></p>
    <p>VERIDIAN transaction state: <strong>{attempt.state}</strong></p>
    <p>Provider observation: <strong>{
      attempt.provider_observation?.provider_status
      ||'Not yet recorded'
    }</strong></p>
    <p>Retained documents: <strong>{
      attempt.retained_documents?.length||0
    }</strong></p>
    {canRead&&<>
      <label style={{
        display:'flex',
        alignItems:'flex-start',
        gap:'10px',
        marginBottom:'12px'
      }}>
        <input type="checkbox"
          checked={confirmed}
          style={{width:'auto',flex:'0 0 auto',margin:'3px 0 0'}}
          onChange={event=>setConfirmed(event.target.checked)}/>
        <span>I authorize a read-only DocuSign check of this
          existing fictional envelope. Do not send another invitation.</span>
      </label>
      <button type="button" className="quiet"
        disabled={busy||working||!confirmed}
        onClick={()=>void connectRead()}>
        Verify existing DocuSign envelope
      </button>
    </>}
    <button type="button" className="quiet"
      disabled={busy||working}
      onClick={()=>void run(refresh)}>
      Refresh existing envelope status
    </button>
    <p className="muted">
      Verified results remain sandbox-only.
      They do not authorize installation, payment,
      or operational customer signatures.
    </p>
  </section>;
}

function CommercialSandboxSend5610({
  packageId,api,busy,run
}:{
  packageId:string;api:API;busy:boolean;run:Run
}){
  const [status,setStatus]=useState<CommercialSendStatus5610|null>(null);
  const [error,setError]=useState('');
  const [fictional,setFictional]=useState(false);
  const [recipients,setRecipients]=useState(false);
  const [working,setWorking]=useState(false);

  const path=`release-packages/${packageId}/commercial-signing/`;

  const refresh=async()=>{
    const result=await api<CommercialSendStatus5610>(path);
    setStatus(result);
    setError('');
  };

  useEffect(()=>{
    let cancelled=false;
    api<CommercialSendStatus5610>(path)
      .then(result=>{if(!cancelled)setStatus(result);})
      .catch(cause=>{
        if(!cancelled)setError(
          cause instanceof Error?cause.message:String(cause)
        );
      });
    return ()=>{cancelled=true;};
  },[path,api]);

  const eligible=status?.sandbox_only===true
    &&status.release?.status==='APPROVED'
    &&status.attempt===null;

  async function connect(){
    if(!eligible||!fictional||!recipients||working)return;
    setWorking(true);
    try{
      await run(async()=>{
        const latest=await api<CommercialSendStatus5610>(path);
        setStatus(latest);
        if(
          latest.sandbox_only!==true
          ||latest.release?.status!=='APPROVED'
          ||latest.attempt!==null
        ){
          throw new Error(
            'Release approval or signing-attempt status changed. Stop.'
          );
        }
        const result=await api<{
          authorization_url:string;envelope_sent:boolean;
          environment:string;attempt_id:string
        }>(path,'POST',{
          fictional_project_confirmed:true,
          controlled_recipients_confirmed:true
        });
        if(
          result.envelope_sent!==false
          ||result.environment!=='SANDBOX'
          ||!result.attempt_id
        ){
          throw new Error('Unexpected commercial authorization response.');
        }
        const url=new URL(result.authorization_url);
        if(
          url.protocol!=='https:'
          ||!(
            url.hostname==='docusign.com'
            ||url.hostname.endsWith('.docusign.com')
            ||url.hostname==='docusign.net'
            ||url.hostname.endsWith('.docusign.net')
          )
        ){
          throw new Error('Unexpected DocuSign authorization destination.');
        }
        window.location.assign(url.href);
      });
    }catch(cause){
      setError(cause instanceof Error?cause.message:String(cause));
    }finally{
      setWorking(false);
    }
  }

  return <section className="sandbox-package">
    <h4>Controlled fictional DocuSign test</h4>
    <p>Sales Manager or CEO only. This starts authorization for
      one sandbox transaction using the exact approved Contract,
      Invoice and recipient identities. No operational signing
      or installation authorization is established.</p>
    {error&&<p role="alert">{error}</p>}
    {!status&&<p>Checking approved commercial package...</p>}
    {status&&<p>Release: <strong>{status.release.status}</strong>.
      {status.attempt
        ?' An attempt already exists; inspect its status instead of retrying.'
        :' No commercial signing attempt recorded.'}</p>}
    {eligible&&<>
      <label style={{display:'flex',alignItems:'flex-start',gap:'10px',marginBottom:'12px'}}>
        <input type="checkbox" checked={fictional}
          style={{width:'auto',flex:'0 0 auto',margin:'3px 0 0'}}
          onChange={event=>setFictional(event.target.checked)}/>
        <span>I confirm this selected project is fictional and the documents
        are sandbox-only tests.</span>
      </label>
      <label style={{display:'flex',alignItems:'flex-start',gap:'10px',marginBottom:'12px'}}>
        <input type="checkbox" checked={recipients}
          style={{width:'auto',flex:'0 0 auto',margin:'3px 0 0'}}
          onChange={event=>setRecipients(event.target.checked)}/>
        <span>I reviewed the exact approved customer and GECC
        signer names, email addresses and customer-first routing.
        Both inboxes are controlled for this test.</span>
      </label>
      <button type="button" className="quiet"
        disabled={busy||working||!fictional||!recipients}
        onClick={()=>void connect()}>
        Connect DocuSign for fictional signing test
      </button>
    </>}
    <button type="button" className="quiet"
      disabled={busy||working}
      onClick={()=>void run(refresh)}>
      Refresh controlled signing readiness
    </button>
    <p className="muted">Backend commercial sending remains
      independently disabled until separately activated.
      If a request fails or its outcome is uncertain,
      do not initiate another attempt.</p>
  </section>;
}

export function ReleaseReview({planId,current,actorId,actorRole,comptroller,busy,api,run}:{planId:string;current:boolean;actorId:string;actorRole:string;comptroller:boolean;busy:boolean;api:API;run:Run}){
 const [packages,setPackages]=useState<Package[]>([]),[error,setError]=useState('');const path=`signing-reviews/${planId}/release-packages/`;
 useEffect(()=>{let closed=false;api<Package[]>(path).then(p=>{if(!closed)setPackages(p);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[path,api]);
 return <div className="sandbox-package"><h4>Release document review</h4><p>This separate review uses recorded cancellation or completion evidence. A different authorized person must approve the package. Approval does not enable sending.</p>{error&&<p role="alert" className="error">{error}</p>}
 {current&&<button className="quiet" type="button" disabled={busy} onClick={()=>void run(async()=>{await api(path,'POST',{});setPackages(await api<Package[]>(path));})}>Prepare release review package</button>}
 <button className="quiet" type="button" disabled={busy} onClick={()=>void run(async()=>setPackages(await api<Package[]>(path)))}>Refresh release review</button>
 {packages.map(pkg=><div key={pkg.id}>{pkg.documents.some(d=>d.kind==='CONTRACT') && pkg.documents.some(d=>d.kind==='INVOICE') && <><CommercialSigningStatus packageId={pkg.id} api={api} busy={busy} run={run}/><CommercialRead5623 packageId={pkg.id} api={api} busy={busy} run={run}/></>}{current&&(actorRole==='SALES_MANAGER'||actorRole==='CEO')&&pkg.release.status==='APPROVED'&&<CommercialSandboxSend5610 packageId={pkg.id} api={api} busy={busy} run={run}/>} <p><time dateTime={pkg.created_at} title="Package creation date and time">{packageDate.format(new Date(pkg.created_at))}</time> · Release review: <strong>{pkg.release.status.replaceAll('_',' ')}</strong></p><ul>{pkg.documents.map(d=><li key={d.kind}><a href={d.download_url}>Download release {d.kind.toLowerCase().replaceAll('_',' ')}</a></li>)}</ul>{pkg.release.blockers.map(b=><p key={b}>{b}</p>)}{pkg.decisions.map((d,i)=><p key={i}>{d.decision} · {d.note}</p>)}
 {current&&pkg.release.status!=='BLOCKED'&&<form onSubmit={e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.currentTarget));void run(async()=>{await api(`release-packages/${pkg.id}/decisions/`,'POST',{...f,documents_and_evidence_reviewed:f.documents_and_evidence_reviewed==='on'});setPackages(await api<Package[]>(path));});}}><label>Release decision<select name="decision"><option value="APPROVED">Approve reviewed package</option><option value="REVOKED">Revoke approval</option></select></label><label>Release review note<textarea name="note" required maxLength={2000}/></label><label className="sandbox-confirm"><input type="checkbox" name="documents_and_evidence_reviewed"/>I reviewed these exact documents, recipient identities, routing and referenced verification evidence.</label>{pkg.created_by===actorId&&<p>Approval requires another authorized reviewer; you can record a revocation.</p>}<button disabled={busy}>Record release decision</button></form>}<SigningTest sourceId={pkg.id} sourceApproved={pkg.release.status==='APPROVED'} comptroller={comptroller} actorId={actorId} busy={busy} api={api} run={run}/></div>)}
 </div>;
}
