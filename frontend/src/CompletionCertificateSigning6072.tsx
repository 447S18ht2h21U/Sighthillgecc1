import { useEffect, useRef, useState } from 'react';

type Api = <T,>(
  path:string,
  method?:string,
  data?:unknown
)=>Promise<T>;

const ENVELOPE='451126d1-b943-889f-81df-12b98cb11a4a';

const RECIPIENT='doug@sighthill.net';

type SendStatus = {
  project_id:string;
  package_id:string;
  package_digest:string;
  envelope_id:string;
  recipient:string;
  state:string;
  provider_status:string|null;
  send_available:boolean;
  blockers:string[];
  fictional:boolean;
  automatic_retry_allowed:boolean;
  operational_send_authorized:boolean;
  completion_authorized:boolean;
};

type RetainedDocument = {
  document_id:string;
  kind:string;
  pdf_sha256:string;
  pages:number;
  size_bytes:number;
  pdf_base64:string;
};

type ReadStatus = {
  project_id:string;
  msr_id:string;
  envelope_id:string;
  retained:boolean;
  retained_at:string|null;
  documents:RetainedDocument[];
  read_available:boolean;
  fictional:boolean;
  read_only:boolean;
  operational_signature_verified:boolean;
  financial_posting_authorized:boolean;
  completion_authorized:boolean;
};

type Authorization = {
  authorization_url:string;
  operation:string;
  environment:string;
  completion_authorized:boolean;
  read_only?:boolean;
  operational_send_authorized?:boolean;
  fictional?:boolean;
  envelope_id?:string;
  recipient?:string;
};

type PdfLink = {
  label:string;
  url:string;
  hash:string;
};

export function CompletionCertificateSigning6072({
  api,
  projectId,
  msrId,
  packageId,
  packageDigest,
  envelopeId,
}:{
  api:Api;
  projectId:string;
  msrId:string;
  packageId:string;
  packageDigest:string;
  envelopeId:string;
}){

  const [send,setSend]=useState<SendStatus|null>(null);

  const [read,setRead]=useState<ReadStatus|null>(null);

  const [links,setLinks]=useState<PdfLink[]>([]);

  const [busy,setBusy]=useState(false);

  const [error,setError]=useState('');

  const [authorization,setAuthorization]=useState<{
    url:string;
    label:string;
  }|null>(null);

  const pending=useRef(false);

  const active=useRef(true);

  const urls=useRef<string[]>([]);

  useEffect(()=>{

    active.current=true;

    return ()=>{

      active.current=false;

      urls.current.forEach(url=>URL.revokeObjectURL(url));

      urls.current=[];
    };

  },[]);

  async function perform(
    operation:()=>Promise<void>
  ){

    if(pending.current)return;

    pending.current=true;

    setBusy(true);

    setError('');

    setAuthorization(null);

    try{

      await operation();

    }catch(err){

      if(active.current){

        setError(
          err instanceof Error
            ?err.message
            :'Unable to complete the requested operation.'
        );
      }

    }finally{

      pending.current=false;

      if(active.current)setBusy(false);
    }
  }

  function checkSend(value:SendStatus){

    if(
      envelopeId!==ENVELOPE||
      value.project_id!==projectId||
      value.package_id!==packageId||
      value.package_digest!==packageDigest||
      value.envelope_id!==ENVELOPE||
      value.recipient!==RECIPIENT||
      value.fictional!==true||
      value.automatic_retry_allowed!==false||
      value.operational_send_authorized!==false||
      value.completion_authorized!==false||
      typeof value.send_available!=='boolean'||
      !Array.isArray(value.blockers)||
      ![
        'NOT_SENT',
        'SEND_OBSERVED',
        'RECONCILIATION_REQUIRED',
      ].includes(value.state)||
      (
        value.send_available&&
        value.state!=='NOT_SENT'
      )
    ){

      throw new Error(
        'Transmission status does not match the fictional envelope.'
      );
    }
  }

  async function refresh(){

    await perform(async()=>{

      setSend(null);

      setRead(null);

      setLinks([]);

      urls.current.forEach(url=>URL.revokeObjectURL(url));

      urls.current=[];

      const result=await api<SendStatus>(
        `completion-certificate-send/${projectId}/`
      );

      checkSend(result);

      if(!active.current)return;

      setSend(result);

      const retained=await api<ReadStatus>(
        `completion-certificate-read/${projectId}/`
      );

      if(
        retained.project_id!==projectId||
        retained.msr_id!==msrId||
        retained.envelope_id!==ENVELOPE||
        retained.fictional!==true||
        retained.read_only!==true||
        retained.operational_signature_verified!==false||
        retained.financial_posting_authorized!==false||
        retained.completion_authorized!==false||
        typeof retained.retained!=='boolean'||
        typeof retained.read_available!=='boolean'||
        !Array.isArray(retained.documents)||
        (
          retained.retained
            ?retained.documents.length!==2
            :retained.documents.length!==0
        )
      ){

        throw new Error(
          'Retrieved evidence does not match the fictional envelope.'
        );
      }

      const created:PdfLink[]=[];

      try{

        if(retained.retained){

          const ids=new Set(
            retained.documents.map(row=>row.document_id)
          );

          if(
            ids.size!==2||
            !ids.has('1')||
            !ids.has('certificate')
          ){

            throw new Error(
              'The retained document inventory is incomplete.'
            );
          }
        }

        for(const row of retained.documents){

          if(
            !Number.isInteger(row.size_bytes)||
            row.size_bytes<1||
            row.size_bytes>8*1024*1024||
            row.pdf_base64.length>12*1024*1024||
            !/^[a-f0-9]{64}$/.test(row.pdf_sha256)
          ){

            throw new Error('Invalid retained PDF metadata.');
          }

          const bytes=Uint8Array.from(
            atob(row.pdf_base64),
            character=>character.charCodeAt(0)
          );

          if(
            bytes.length!==row.size_bytes||
            String.fromCharCode(...bytes.slice(0,5))!=='%PDF-'
          ){

            throw new Error('Invalid retained PDF content.');
          }

          const digest=await crypto.subtle.digest(
            'SHA-256',
            bytes
          );

          const actual=Array.from(
            new Uint8Array(digest)
          ).map(
            value=>value.toString(16).padStart(2,'0')
          ).join('');

          if(actual!==row.pdf_sha256){

            throw new Error(
              'Retained PDF fingerprint does not match.'
            );
          }

          const url=URL.createObjectURL(
            new Blob(
              [bytes],
              {type:'application/pdf'}
            )
          );

          created.push({
            label:row.document_id==='1'
              ?'View signed Completion Certificate'
              :'View DocuSign Certificate of Completion',
            url,
            hash:actual,
          });
        }

      }catch(err){

        created.forEach(
          item=>URL.revokeObjectURL(item.url)
        );

        throw err;
      }

      if(!active.current){

        created.forEach(
          item=>URL.revokeObjectURL(item.url)
        );

        return;
      }

      urls.current=created.map(item=>item.url);

      setLinks(created);

      setRead(retained);
    });
  }

  async function authorize(mode:'send'|'read'){

    if(pending.current||authorization)return;

    if(mode==='send'&&send?.send_available!==true)return;

    if(mode==='read'&&read?.read_available!==true)return;

    const question=mode==='send'
      ?'Send the existing fictional Completion Certificate to '
        +RECIPIENT+'? No actual customer or lender is involved.'
      :'Check the existing DocuSign envelope and retrieve completed '
        +'fictional signing evidence, if available?';

    if(!window.confirm(question))return;

    await perform(async()=>{

      const result=await api<Authorization>(
        `completion-certificate-${mode}/${projectId}/`,
        'POST',
        mode==='send'
          ?{
            envelope_id:ENVELOPE,
            recipient:RECIPIENT,
            confirmed:true,
          }
          :{
            envelope_id:ENVELOPE,
            confirmed:true,
          }
      );

      const url=new URL(result.authorization_url);

      if(
        result.environment!=='SANDBOX'||
        result.completion_authorized!==false||
        result.operation!==(
          mode==='send'
            ?'SANDBOX_CERTIFICATE_SEND_6071'
            :'SANDBOX_CERTIFICATE_READ_6069'
        )||
        url.origin!=='https://account-d.docusign.com'||
        url.pathname!=='/oauth/auth'||
        url.username||
        url.password||
        url.hash||
        url.searchParams.get('response_type')!=='code'||
        !url.searchParams.get('state')||
        (
          mode==='send'&&(
            result.envelope_id!==ENVELOPE||
            result.recipient!==RECIPIENT||
            result.fictional!==true||
            result.operational_send_authorized!==false
          )
        )||
        (
          mode==='read'&&result.read_only!==true
        )
      ){

        throw new Error(
          'Unexpected DocuSign authorization response.'
        );
      }

      if(!active.current)return;

      setAuthorization({
        url:url.href,
        label:mode==='send'
          ?'Connect to DocuSign and send test certificate'
          :'Connect to DocuSign and retrieve certificate',
      });
    });
  }

  return (
    <div className="inspection-purchase-6041">

      <strong>Completion Certificate signing test</strong>

      <p>
        Test recipient: <strong>{RECIPIENT}</strong>
      </p>

      <p>
        Only the existing fictional DocuSign envelope
        can be sent.
      </p>

      <button
        type="button"
        className="quiet"
        disabled={busy}
        onClick={()=>void refresh()}
      >
        {busy
          ?'Checking...'
          :'Check certificate signing status'}
      </button>

      {send?.state==='NOT_SENT'&&
        <p>Test certificate has not been sent.</p>}

      {send?.state==='NOT_SENT'&&
        send.blockers.map((blocker,index)=>
          <p key={index}>{blocker}</p>
        )}

      {send?.send_available&&!authorization&&
        <button
          type="button"
          disabled={busy}
          onClick={()=>void authorize('send')}
        >
          Send test Completion Certificate
        </button>}

      {send?.state==='SEND_OBSERVED'&&
        <div className="inspection-success-6041">

          <strong>Test Completion Certificate sent</strong>

          <p>
            DocuSign transmission recorded.
            Check {RECIPIENT} for the signing invitation.
          </p>

          <p>
            Do not sign if the document or signature
            placement is incorrect.
          </p>

        </div>}

      {send?.state==='RECONCILIATION_REQUIRED'&&
        <div className="inspection-warning-6041">

          <strong>Transmission requires review</strong>

          <p>
            Do not send again or create another envelope.
          </p>

        </div>}

      {read?.read_available&&
        !read.retained&&
        !authorization&&
        <button
          type="button"
          className="quiet"
          disabled={busy}
          onClick={()=>void authorize('read')}
        >
          Retrieve signed test certificate
        </button>}

      {authorization&&
        <div>

          <p>
            Authenticate in the new browser tab.
            Return here afterward and check the signing status.
          </p>

          <a
            href={authorization.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {authorization.label}
          </a>

        </div>}

      {read?.retained&&
        <div className="inspection-success-6041">

          <strong>Signed test certificate retained</strong>

          {read.retained_at&&
            <p>
              Retained: {new Date(
                read.retained_at
              ).toLocaleString(
                'en-US',
                {timeZone:'America/New_York'}
              )} ET
            </p>}

          {links.map(item=>
            <p key={item.hash+item.label}>

              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {item.label}
              </a>

            </p>
          )}

          <p>
            Both retained PDF fingerprints verified.
          </p>

        </div>}

      {error&&
        <p className="error" role="alert">
          {error}
        </p>}

      <p>
        Fictional test only. No operational completion,
        payment or funding authorization.
      </p>

    </div>
  );
}
