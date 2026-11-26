import { useEffect, useRef, useState } from 'react';
import {
  CompletionCertificateDraft6064,
} from './CompletionCertificateDraft6064';

type Api = <T,>(
  path:string,
  method?:string,
  data?:unknown
)=>Promise<T>;

type SigningTab = {
  documentId:string;
  recipientId:string;
  pageNumber:string;
  xPosition:string;
  yPosition:string;
  tabLabel:string;
};

type SandboxPackage = {
  project_id:string;
  msr_id:string;
  inspection_id:string;
  certificate_id:string;
  certificate_digest:string;
  certificate_kind:
    'COMPLETION_FINANCED'|'COMPLETION_NON_FINANCED';
  pdf_sha256:string;
  sandbox_recipient:{
    name:string;
    email:string;
    classification:string;
    operational_customer_authority:boolean;
  };
  prepared:boolean;
  package_id:string|null;
  package_digest:string|null;
  prepared_at:string|null;
  layout:{
    tabs:{
      signHereTabs:SigningTab[];
      dateSignedTabs:SigningTab[];
    };
    provider_layout_verified:boolean;
  }|null;
  fictional:boolean;
  signed:boolean;
  provider_authenticated:boolean;
  provider_layout_verified:boolean;
  sandbox_send_authorized:boolean;
  certificate_send_authorized:boolean;
  operational_customer_authority:boolean;
  completion_authorized:boolean;
};

const DESIGNATED_RECIPIENT='doug@sighthill.net';

const isDigest=(value:unknown):value is string=>
  typeof value==='string'&&/^[a-f0-9]{64}$/i.test(value);

export function CompletionCertificateSandbox6058({
  api,
  projectId,
  msrId,
  inspectionId,
  certificateId,
  certificateDigest,
  pdfSha256,
  certificateKind,
}:{
  api:Api;
  projectId:string;
  msrId:string;
  inspectionId:string;
  certificateId:string;
  certificateDigest:string;
  pdfSha256:string;
  certificateKind:SandboxPackage['certificate_kind'];
}){

  const [review,setReview]=useState<SandboxPackage|null>(null);

  const [busy,setBusy]=useState(false);

  const [error,setError]=useState('');

  const pending=useRef(false);

  const active=useRef(true);

  useEffect(()=>{

    active.current=true;

    return ()=>{

      active.current=false;
    };

  },[]);

  function validate(result:SandboxPackage){

    if(
      result.project_id!==projectId||
      result.msr_id!==msrId||
      result.inspection_id!==inspectionId||
      result.certificate_id!==certificateId||
      result.certificate_digest!==certificateDigest||
      result.certificate_kind!==certificateKind||
      result.pdf_sha256!==pdfSha256||
      !isDigest(result.pdf_sha256)||
      result.fictional!==true||
      result.signed!==false||
      result.provider_authenticated!==false||
      result.provider_layout_verified!==false||
      result.sandbox_send_authorized!==false||
      result.certificate_send_authorized!==false||
      result.operational_customer_authority!==false||
      result.completion_authorized!==false||
      typeof result.prepared!=='boolean'||
      result.sandbox_recipient?.email!==DESIGNATED_RECIPIENT||
      result.sandbox_recipient?.name!=='GECC Test Customer'||
      result.sandbox_recipient?.classification!==
        'DESIGNATED_SANDBOX_RECIPIENT'||
      result.sandbox_recipient?.operational_customer_authority!==false
    ){

      throw new Error(
        'Signing package does not match the retained fictional certificate.'
      );
    }

    if(result.prepared){

      if(
        !result.package_id||
        !isDigest(result.package_digest)||
        !result.prepared_at||
        result.layout?.provider_layout_verified!==false
      ){

        throw new Error(
          'Retained signing package requires review.'
        );
      }

      const signature=result.layout.tabs.signHereTabs;

      const dates=result.layout.tabs.dateSignedTabs;

      if(
        !Array.isArray(signature)||
        signature.length!==1||
        signature[0].tabLabel!=='customer_signature'||
        !Array.isArray(dates)||
        dates.length!==2||
        !dates.some(tab=>
          tab.tabLabel==='customer_signed_date'
        )||
        !dates.some(tab=>
          tab.tabLabel==='acknowledgment_date'
        )
      ){

        throw new Error(
          'Certificate signature or date instructions require review.'
        );
      }

      for(const tab of [...signature,...dates]){

        const x=Number(tab.xPosition);

        const y=Number(tab.yPosition);

        if(
          tab.documentId!=='1'||
          tab.recipientId!=='1'||
          tab.pageNumber!=='1'||
          !Number.isInteger(x)||
          !Number.isInteger(y)||
          x<0||x>=612||
          y<0||y>=792
        ){

          throw new Error(
            'Certificate signing field position requires review.'
          );
        }
      }
    }

    return result;
  }

  async function request(prepare:boolean){

    if(pending.current)return;

    pending.current=true;

    setBusy(true);

    setError('');

    try{

      const result=await api<SandboxPackage>(
        `completion-certificate-sandbox/${projectId}/`,
        prepare?'POST':'GET',
        prepare?{
          expected_certificate_id:certificateId,
          expected_certificate_digest:certificateDigest,
          sandbox_recipient:DESIGNATED_RECIPIENT,
          fictional_confirmed:true,
        }:undefined
      );

      if(!active.current)return;

      const validated=validate(result);

      if(prepare&&validated.prepared!==true){

        throw new Error(
          'Sandbox signing package was not retained.'
        );
      }

      setReview(validated);

    }catch(err){

      if(active.current){

        setReview(null);

        setError(
          err instanceof Error
            ?err.message
            :'Sandbox signing preparation could not be completed.'
        );
      }

    }finally{

      pending.current=false;

      if(active.current)setBusy(false);
    }
  }

  return (
    <div className="inspection-purchase-6041">

      <strong>DocuSign sandbox preparation</strong>

      <p>
        Fictional test only. No actual customer signing
        authority or payment authorization is established.
      </p>

      {!review&&
        <button
          type="button"
          className="quiet"
          disabled={busy}
          onClick={()=>void request(false)}
        >
          {busy
            ?'Checking signing recipient...'
            :'Review sandbox signing recipient'}
        </button>}

      {review&&<>

        <p>
          <strong>Sandbox recipient:</strong>{' '}
          {review.sandbox_recipient.email}
        </p>

        <p>
          <strong>Fictional customer:</strong>{' '}
          {review.sandbox_recipient.name}
        </p>

        {!review.prepared&&
          <>

            <p>
              VERIDIAN will retain the signing instructions
              for the original prepared certificate.
              No document will be sent.
            </p>

            <button
              type="button"
              disabled={busy}
              onClick={()=>{

                if(window.confirm(
                  'Prepare and retain this fictional DocuSign signing package for '
                  +DESIGNATED_RECIPIENT+
                  '? No document will be sent.'
                )){

                  void request(true);
                }
              }}
            >
              {busy
                ?'Preparing signing package...'
                :'Prepare sandbox signing package'}
            </button>

          </>}

        {review.prepared&&
          <div
            className="inspection-success-6041"
            role="status"
          >

            <strong>Sandbox signing package retained</strong>

            {review.prepared_at&&
              <p>
                Prepared: {
                  new Date(
                    review.prepared_at
                  ).toLocaleString('en-US',{
                    timeZone:'America/New_York',
                  })
                } ET
              </p>}

            <p>
              The original Completion Certificate and
              designated sandbox recipient are preserved.
            </p>

            <p>
              Signing instructions: Customer Signature,
              Signature Date and Acknowledgment Date.
            </p>

            <button
              type="button"
              className="quiet"
              disabled={busy}
              onClick={()=>void request(false)}
            >
              Retrieve retained signing package
            </button>

          </div>}

        {review.prepared&&
          review.package_id&&
          review.package_digest&&
          <CompletionCertificateDraft6064
            key={review.package_digest}
            api={api}
            projectId={projectId}
            msrId={msrId}
            packageId={review.package_id}
            packageDigest={review.package_digest}
            certificateId={certificateId}
            pdfSha256={pdfSha256}
          />}

        <div className="inspection-warning-6041">

          <strong>DocuSign transmission unavailable</strong>

          <p>
            Only unsent sandbox draft creation is supported.
            Sending remains disabled.
          </p>

        </div>

      </>}

      {error&&
        <p className="error" role="alert">
          {error}
        </p>}

    </div>
  );
}
