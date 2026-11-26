import { useEffect, useRef, useState } from 'react';
import { CompletionCertificateSigning6072 } from './CompletionCertificateSigning6072';

type Api = <T,>(
  path:string,
  method?:string,
  data?:unknown
)=>Promise<T>;

type DraftStatus = {
  project_id:string;
  msr_id:string;
  package_id:string;
  package_digest:string;
  certificate_id:string;
  pdf_sha256:string;
  recipient:string;
  state:string;
  envelope_id:string|null;
  metadata_verified:boolean;
  visual_layout_verified:boolean;
  provider_pdf_content_verified:boolean;
  reconciliation_required:boolean;
  create_available:boolean;
  configuration_blockers:string[];
  fictional:boolean;
  send_authorized:boolean;
  completion_authorized:boolean;
  automatic_retry_allowed:boolean;
};

type Authorization = {
  authorization_url:string;
  environment:string;
  operation:string;
  expires_at:string;
  send_authorized:boolean;
  completion_authorized:boolean;
};

export function CompletionCertificateDraft6064({
  api,
  projectId,
  msrId,
  packageId,
  packageDigest,
  certificateId,
  pdfSha256,
}:{
  api:Api;
  projectId:string;
  msrId:string;
  packageId:string;
  packageDigest:string;
  certificateId:string;
  pdfSha256:string;
}){

  const [status,setStatus]=useState<DraftStatus|null>(null);

  const [busy,setBusy]=useState(false);

  const [error,setError]=useState('');

  const [authorizationUrl,setAuthorizationUrl]=useState('');

  const pending=useRef(false);

  const active=useRef(true);

  useEffect(()=>{

    active.current=true;

    return ()=>{

      active.current=false;
    };

  },[]);

  async function refresh(){

    if(pending.current)return;

    pending.current=true;

    setBusy(true);

    setError('');

    setAuthorizationUrl('');

    try{

      const result=await api<DraftStatus>(
        `completion-certificate-provider/${projectId}/`
      );

      if(!active.current)return;

      if(
        result.project_id!==projectId||
        result.msr_id!==msrId||
        result.package_id!==packageId||
        result.package_digest!==packageDigest||
        result.certificate_id!==certificateId||
        result.pdf_sha256!==pdfSha256||
        result.recipient!=='doug@sighthill.net'||
        result.fictional!==true||
        result.send_authorized!==false||
        result.completion_authorized!==false||
        result.automatic_retry_allowed!==false||
        result.visual_layout_verified!==false||
        result.provider_pdf_content_verified!==false||
        ![
          'NO_DRAFT',
          'PROVIDER_OUTCOME_UNKNOWN',
          'CREATED_UNVALIDATED',
          'DRAFT_METADATA_VALIDATED',
        ].includes(result.state)||
        typeof result.create_available!=='boolean'||
        typeof result.reconciliation_required!=='boolean'||
        !Array.isArray(result.configuration_blockers)||
        (
          result.create_available&&
          (
            result.state!=='NO_DRAFT'||
            result.envelope_id!==null||
            result.reconciliation_required
          )
        )
      ){

        throw new Error(
          'Draft status does not match the retained signing package.'
        );
      }

      setStatus(result);

    }catch(err){

      if(active.current){

        setStatus(null);

        setError(
          err instanceof Error
            ?err.message
            :'Unable to check DocuSign draft status.'
        );
      }

    }finally{

      pending.current=false;

      if(active.current)setBusy(false);
    }
  }

  async function authorize(){

    if(
      pending.current||
      status?.create_available!==true||
      authorizationUrl
    )return;

    if(!window.confirm(
      'Create an unsent fictional DocuSign sandbox draft for '
      +'doug@sighthill.net? No signing invitation will be sent.'
    ))return;

    pending.current=true;

    setBusy(true);

    setError('');

    try{

      const result=await api<Authorization>(
        `completion-certificate-provider/${projectId}/`,
        'POST',
        {
          expected_package_id:packageId,
          expected_package_digest:packageDigest,
          confirmed:true,
        }
      );

      if(!active.current)return;

      const url=new URL(result.authorization_url);

      if(
        result.environment!=='SANDBOX'||
        result.operation!=='SANDBOX_CERTIFICATE_DRAFT_6063'||
        result.send_authorized!==false||
        result.completion_authorized!==false||
        url.origin!=='https://account-d.docusign.com'||
        url.pathname!=='/oauth/auth'||
        url.username||
        url.password||
        url.hash||
        url.searchParams.get('response_type')!=='code'||
        !url.searchParams.get('state')
      ){

        throw new Error(
          'Unexpected DocuSign authorization response.'
        );
      }

      setAuthorizationUrl(url.href);

    }catch(err){

      if(active.current){

        setAuthorizationUrl('');

        setStatus(null);

        setError(
          err instanceof Error
            ?err.message
            :'DocuSign draft authorization could not be started.'
        );
      }

    }finally{

      pending.current=false;

      if(active.current)setBusy(false);
    }
  }

  return (
    <div className="inspection-purchase-6041">

      <strong>DocuSign sandbox draft</strong>

      <p>
        Create the original Completion Certificate
        in DocuSign without sending it.
      </p>

      <button
        type="button"
        className="quiet"
        disabled={busy}
        onClick={()=>void refresh()}
      >
        {busy
          ?'Checking DocuSign...'
          :'Check DocuSign draft status'}
      </button>

      {status&&<>

        {status.state==='NO_DRAFT'&&
          <p>No DocuSign draft has been created.</p>}

        {status.configuration_blockers.length>0&&
          status.state==='NO_DRAFT'&&
          <div className="inspection-warning-6041">

            {status.configuration_blockers.map(
              (blocker,index)=>
                <p key={index}>{blocker}</p>
            )}

          </div>}

        {status.create_available&&!authorizationUrl&&
          <button
            type="button"
            disabled={busy}
            onClick={()=>void authorize()}
          >
            Create DocuSign sandbox draft
          </button>}

        {status.envelope_id&&
          <p>
            <strong>DocuSign envelope ID:</strong>{' '}
            {status.envelope_id}
          </p>}

        {status.metadata_verified&&
          <div
            className="inspection-success-6041"
            role="status"
          >

            <strong>
              Unsent DocuSign draft created
            </strong>

            <p>
              Recipient, document inventory and signing
              field positions checked against the retained package.
            </p>

            <p>
              Review the actual document and signature
              fields in DocuSign before sending.
            </p>

          </div>}

        {status.reconciliation_required&&
          <div className="inspection-warning-6041">

            <strong>Existing draft requires review</strong>

            <p>
              Do not create another envelope.
              The previous provider attempt must be reconciled.
            </p>

          </div>}

      </>}

      {status?.metadata_verified===true&&
        status.envelope_id&&
        <CompletionCertificateSigning6072
          key={status.envelope_id}
          api={api}
          projectId={projectId}
          msrId={msrId}
          packageId={packageId}
          packageDigest={packageDigest}
          envelopeId={status.envelope_id}
        />}

      {authorizationUrl&&
        <div>

          <p>
            Connect to the DocuSign sandbox account
            in a new browser tab. After authentication,
            return here and check the draft status.
          </p>

          <p>
            <a
              href={authorizationUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              Connect to DocuSign sandbox
            </a>
          </p>

        </div>}

      {error&&
        <p className="error" role="alert">
          {error}
        </p>}

      <p>
        Fictional test only. No operational signing
        or project completion authorization.
      </p>

    </div>
  );
}
