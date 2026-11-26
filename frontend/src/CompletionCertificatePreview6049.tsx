import { useEffect, useRef, useState } from 'react';
import {
  CompletionCertificateSandbox6058,
} from './CompletionCertificateSandbox6058';

type Api = <T,>(
  path:string,
  method?:string,
  data?:unknown
)=>Promise<T>;

type Preview = {
  project_id:string;
  msr_id:string;
  inspection_id:string;
  kind:'COMPLETION_FINANCED'|'COMPLETION_NON_FINANCED';
  pdf_base64:string;
  pdf_sha256:string;
  retained:boolean;
  retained_certificate_id:string|null;
  retained_certificate_digest:string|null;
  prepared_at:string|null;
  recipient_status:string;
  recipient_authorized:boolean;
  fictional_preview:boolean;
  signed:boolean;
  certificate_send_authorized:boolean;
  completion_authorized:boolean;
};

type DisplayPreview = {
  url:string;
  kind:Preview['kind'];
  retained:boolean;
  preparedAt:string|null;
  recipientStatus:string;
  certificateId:string|null;
  certificateDigest:string|null;
  pdfSha256:string;
};

export function CompletionCertificatePreview6049({
  api,
  projectId,
  msrId,
  inspectionId,
}:{
  api:Api;
  projectId:string;
  msrId:string;
  inspectionId:string;
}){

  const [busy,setBusy]=useState(false);

  const [error,setError]=useState('');

  const [preview,setPreview]=useState<DisplayPreview|null>(null);

  const objectUrl=useRef<string|null>(null);

  const active=useRef(true);

  const pending=useRef(false);

  useEffect(()=>{

    active.current=true;

    return ()=>{

      active.current=false;

      if(objectUrl.current){

        URL.revokeObjectURL(objectUrl.current);

        objectUrl.current=null;
      }
    };

  },[]);

  async function prepare(retain:boolean){

    if(pending.current)return;

    pending.current=true;

    setBusy(true);

    setError('');

    try{

      const result=await api<Preview>(
        `completion-certificate-preview/${projectId}/`,
        retain?'POST':'GET',
        retain?{
          expected_msr_id:msrId,
          expected_inspection_id:inspectionId,
          fictional_retention_confirmed:true,
        }:undefined
      );

      if(!active.current)return;

      if(
        result.project_id!==projectId||
        result.msr_id!==msrId||
        result.inspection_id!==inspectionId||
        result.fictional_preview!==true||
        result.signed!==false||
        result.recipient_authorized!==false||
        result.certificate_send_authorized!==false||
        result.completion_authorized!==false||
        typeof result.retained!=='boolean'||
        (retain&&result.retained!==true)||
        (result.retained&&(
          !result.retained_certificate_id||
          !result.retained_certificate_digest
        ))||
        ![
          'COMPLETION_FINANCED',
          'COMPLETION_NON_FINANCED',
        ].includes(result.kind)
      ){

        throw new Error(
          'Certificate does not match the saved inspection.'
        );
      }

      if(
        typeof result.pdf_base64!=='string'||
        result.pdf_base64.length>
          4*Math.ceil(15*1024*1024/3)
      ){

        throw new Error(
          'Certificate exceeds the allowed preview size.'
        );
      }

      const binary=atob(result.pdf_base64);

      if(
        !binary.startsWith('%PDF-')||
        binary.length>15*1024*1024
      ){

        throw new Error(
          'Certificate preview is not a valid PDF.'
        );
      }

      const bytes=new Uint8Array(binary.length);

      for(let index=0;index<binary.length;index++){

        bytes[index]=binary.charCodeAt(index);
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

      if(actual!==result.pdf_sha256){

        throw new Error(
          'Certificate integrity could not be verified.'
        );
      }

      if(!active.current)return;

      const blob=new Blob(
        [bytes],
        {type:'application/pdf'}
      );

      const nextUrl=URL.createObjectURL(blob);

      if(objectUrl.current){

        URL.revokeObjectURL(objectUrl.current);
      }

      objectUrl.current=nextUrl;

      setPreview({
        url:nextUrl,
        kind:result.kind,
        retained:result.retained,
        preparedAt:result.prepared_at,
        recipientStatus:result.recipient_status,
        certificateId:result.retained_certificate_id,
        certificateDigest:result.retained_certificate_digest,
        pdfSha256:result.pdf_sha256,
      });

    }catch(err){

      if(active.current){

        if(objectUrl.current){

          URL.revokeObjectURL(objectUrl.current);

          objectUrl.current=null;
        }

        setPreview(null);

        setError(
          err instanceof Error
            ?err.message
            :'Completion Certificate could not be prepared.'
        );
      }

    }finally{

      pending.current=false;

      if(active.current)setBusy(false);
    }
  }

  return (
    <div className="inspection-purchase-6041">

      <strong>Completion Certificate preview</strong>

      <p>
        VERIDIAN selects the appropriate certificate
        using the approved MSR.
      </p>

      <div className="inspection-actions-6041">

        <button
          type="button"
          disabled={busy}
          onClick={()=>{

            if(preview?.retained){

              void prepare(false);

              return;
            }

            if(window.confirm(
              'Prepare and retain this fictional Completion Certificate?'
            )){

              void prepare(true);
            }
          }}
        >
          {busy
            ?'Preparing certificate...'
            :preview?.retained
              ?'Retrieve retained Completion Certificate'
              :'Prepare Completion Certificate'}
        </button>

        {!preview?.retained&&
          <button
            type="button"
            className="quiet"
            disabled={busy}
            onClick={()=>void prepare(false)}
          >
            View current certificate
          </button>}

      </div>

      {error&&
        <p className="error" role="alert">
          {error}
        </p>}

      {preview&&<>

        {preview.retained&&
          <div
            className="inspection-success-6041"
            role="status"
          >

            <strong>Completion Certificate retained</strong>

            {preview.preparedAt&&
              <p>
                Prepared: {
                  new Date(
                    preview.preparedAt
                  ).toLocaleString('en-US',{
                    timeZone:'America/New_York',
                  })
                } ET
              </p>}

            <p>
              The original prepared document is preserved.
            </p>

          </div>}

        <p
          className="inspection-verified-6041"
          role="status"
        >
          <strong>{
            preview.kind==='COMPLETION_FINANCED'
              ?'FINANCED Completion Certificate'
              :'NOT FINANCED Completion Certificate'
          }</strong>
        </p>

        <p>
          <a
            href={preview.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View Completion Certificate
          </a>
        </p>

        <p>
          <a
            href={preview.url}
            download={
              `GECC-${preview.kind==='COMPLETION_FINANCED'
                ?'FINANCED':'NON-FINANCED'}-PREVIEW.pdf`
            }
          >
            Download Completion Certificate preview
          </a>
        </p>

        {!preview.retained&&
          <p>
            This preview has not been permanently retained.
          </p>}

        {preview.retained&&
          <div className="inspection-warning-6041">

            <strong>Signing recipient required</strong>

            <p>{
              preview.recipientStatus==='RECIPIENT_EMAIL_REQUIRED'
                ?'Customer email is missing. The certificate is retained, but cannot be sent.'
                :'Signing recipient authorization must be established before sending.'
            }</p>

          </div>}

        <p>
          Fictional preview only.
          Not signed or authorized for customer delivery.
        </p>

        {preview.retained&&
          preview.certificateId&&
          preview.certificateDigest&&
          <CompletionCertificateSandbox6058
            key={
              `${projectId}:${msrId}:${inspectionId}:${preview.certificateId}:${preview.certificateDigest}`
            }
            api={api}
            projectId={projectId}
            msrId={msrId}
            inspectionId={inspectionId}
            certificateId={preview.certificateId}
            certificateDigest={preview.certificateDigest}
            pdfSha256={preview.pdfSha256}
            certificateKind={preview.kind}
          />}

      </>}

    </div>
  );
}
