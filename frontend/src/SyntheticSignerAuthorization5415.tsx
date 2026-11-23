import {useEffect, useState} from 'react';

type AuthorizationStatus = {
  requested:boolean;
  approved:boolean;
  synthetic:boolean;
  request_id?:string;
  signer_name?:string;
  signer_email?:string;
  requested_at?:string;
  approved_at?:string;
  authorization_id?:string;
};

type API = <T,>(path:string,method?:string,data?:unknown)=>Promise<T>;

type Props = {
  projectId:string;
  actorRole:string;
  busy:boolean;
  api:API;
  run:(task:()=>Promise<void>)=>void;
};

export function SyntheticSignerAuthorization5415({
  projectId,actorRole,busy,api,run
}:Props) {
  const [status,setStatus]=useState<AuthorizationStatus|null>(null);
  const [error,setError]=useState('');
  const [name,setName]=useState('Fictional Test Customer');
  const [email,setEmail]=useState('fictional.customer@example.invalid');
  const base=`projects/${projectId}/synthetic-signer/`;

  useEffect(()=>{
    let cancelled=false;
    setStatus(null);
    setError('');
    api<AuthorizationStatus>(base+'status/')
      .then(result=>{if(!cancelled)setStatus(result);})
      .catch(err=>{if(!cancelled)setError(String(err.message||err));});
    return()=>{cancelled=true;};
  },[base,api]);

  async function submitRequest() {
    const result=await api<AuthorizationStatus>(
      base+'request/','POST',{
        signer_name:name.trim(),
        signer_email:email.trim().toLowerCase()
      }
    );
    setStatus(result);
  }

  async function approveRequest() {
    const result=await api<AuthorizationStatus>(
      base+'approve/','POST',{approve:true}
    );
    setStatus(result);
  }

  return <section className="veridian-guide-banner veridian-guide-banner--info">
    <h3>Synthetic Customer-Signer Authorization</h3>
    <p>
      Fictional project only. This is test evidence,
      not authorization from a real customer.
      No email or DocuSign request is sent by this panel.
    </p>
    {error&&<p role="alert" className="error">{error}</p>}
    {!status&&!error&&<p>Loading authorization status...</p>}

    {status&&(!status.requested||status.approved)&&actorRole==='SALES_ASSOCIATE'&&
      <form onSubmit={e=>{
        e.preventDefault();
        void run(submitRequest);
      }}>
        <div className="grid">
          <label>Fictional customer signer full name
            <input value={name} onChange={e=>setName(e.target.value)}
              maxLength={250} required/>
          </label>
          <label>Fictional signer email
            <input value={email} onChange={e=>setEmail(e.target.value)}
              type="email" maxLength={254} required/>
          </label>
        </div>
        <p className="muted">
          For Project 104, use a fictional @example.invalid address or a real test inbox explicitly approved in the backend sandbox recipient allowlist. A replacement requires fresh independent approval.
          No real customer permission is asserted.
        </p>
        <button disabled={busy||!name.trim()||
          !email.trim()}>
          {status.requested ? 'Request replacement synthetic signer' : 'Submit synthetic authorization request'}
        </button>
      </form>
    }

    {status&&!status.requested&&actorRole!=='SALES_ASSOCIATE'&&
      <p>Awaiting the assigned Sales Associate's fictional request.</p>
    }

    {status&&status.requested&&<>
      <p><strong>Synthetic request recorded</strong></p>
      <p>Fictional signer: {status.signer_name} ({status.signer_email})</p>
      <p>Requested: {status.requested_at
        ? new Date(status.requested_at).toLocaleString()
        : 'Timestamp unavailable'}</p>
      {status.approved
        ? <p role="status"><strong>
            SYNTHETIC TEST AUTHORIZATION APPROVED
          </strong> — independent manager approval recorded.
          No real customer authority is asserted.</p>
        : actorRole==='SALES_MANAGER'
          ? <div>
              <p>
                Review the fictional signer details before independently
                approving this synthetic test request.
              </p>
              <button disabled={busy} onClick={()=>void run(approveRequest)}>
                Approve synthetic authorization
              </button>
            </div>
          : <p>Awaiting independent Sales Manager approval.</p>
      }
    </>}
    <p className="muted">
      Production customer authorization and DocuSign delivery
      remain subject to their separate safeguards.
    </p>
  </section>;
}
