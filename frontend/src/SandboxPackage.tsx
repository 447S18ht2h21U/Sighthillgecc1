import { useEffect, useState } from 'react';
type API = <T>(path:string, method?:string, data?:unknown)=>Promise<T>;
type Package = {id:string;documents:{kind:string;download_url:string}[];attempt:null|{state:string;envelope_id:string;evidence:{visual_review_required?:boolean}}};
export function SandboxPackage({planId,current,comptroller,busy,api,run}:{planId:string;current:boolean;comptroller:boolean;busy:boolean;api:API;run:(job:()=>Promise<void>)=>Promise<void>}){
 const [pkg,setPackage]=useState<Package|null>(null),[confirmed,setConfirmed]=useState(false),[error,setError]=useState('');
 const path=`signing-reviews/${planId}/sandbox-package/`;
 useEffect(()=>{let closed=false;api<Package|null>(path).then(p=>{if(!closed)setPackage(p);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[path,api]);
 return <div className="sandbox-package"><h4>Sandbox draft test</h4><p>Test copies use the reviewed signer names and preserve the approved project details. They are marked DO NOT SIGN. Cancellation deadlines and completed work remain unverified; live release is blocked.</p>{error&&<p role="alert" className="error">{error}</p>}
 {current&&<button type="button" className="quiet" disabled={busy} onClick={()=>void run(async()=>{setError('');setPackage(await api<Package>(path,'POST',{}));})}>Prepare sandbox package</button>}
 {pkg&&<><ul>{pkg.documents.map(d=><li key={d.kind}><a href={d.download_url}>Download sandbox {d.kind.toLowerCase().replaceAll('_',' ')}</a></li>)}</ul>
 {pkg.attempt&&<p>Draft attempt: <strong>{pkg.attempt.state.replaceAll('_',' ')}</strong>{pkg.attempt.envelope_id&&<> · Envelope {pkg.attempt.envelope_id}</>}{pkg.attempt.state==='RECONCILIATION_REQUIRED'&&' — inspect your existing Docusign sandbox drafts; do not create another copy.'}{pkg.attempt.evidence.visual_review_required&&' — inspect document appearance and tab placement in Docusign Drafts. This does not approve sending.'}</p>}
 <button type="button" className="quiet" disabled={busy} onClick={()=>void run(async()=>setPackage(await api<Package>(path)))}>Refresh sandbox draft status</button>
 {current&&comptroller&&(!pkg.attempt||pkg.attempt.state==='AUTH_PENDING')&&<><label className="sandbox-confirm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I authorize creation of one unsent draft in the configured Docusign sandbox for testing.</label><button type="button" disabled={busy||!confirmed} onClick={()=>void run(async()=>{const result=await api<{authorization_url:string}>(`sandbox-packages/${pkg.id}/connect-draft/`,'POST',{confirm_unsent_sandbox_draft:true});const url=new URL(result.authorization_url);if(url.origin!=='https://account-d.docusign.com'||url.pathname!=='/oauth/auth')throw Error('Unexpected sandbox authorization URL.');window.location.assign(url.href);})}>Authorize unsent sandbox draft</button></>}
 {!comptroller&&current&&<p>The Comptroller authorizes Docusign sandbox draft creation.</p>}</>}
 </div>;
}
