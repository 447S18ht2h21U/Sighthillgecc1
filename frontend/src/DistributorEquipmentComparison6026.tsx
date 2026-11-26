import React from 'react';

export type EquipmentRequirement6026 = {
  model_number:string;
  quantity:number;
};

type ApprovedComparisonRow = {
  approved_model_number:string;
  approved_quantity:number;
  recorded_purchase_quantity:number;
  remaining_quantity:number;
  excess_quantity:number;
  status:string;
};

type PurchaseComparisonRow = {
  observed_model_number:string;
  quantity:number;
  status:string;
  suggested_model_number:string|null;
  possible_matches:string[];
};

type PurchaseComparison = {
  status:string;
  approved_equipment:ApprovedComparisonRow[];
  purchased_equipment:PurchaseComparisonRow[];
  approved_unit_count:number;
  exactly_matched_purchase_unit_count:number;
  unresolved_purchase_row_count:number;
  purchase_identifiers_reconciled:boolean;
};

export type ProjectEquipmentReconciliation6026 = {
  status:string;
  approved_requirements_available:boolean;
  required_equipment:EquipmentRequirement6026[];
  existing_equipment:EquipmentRequirement6026[];
  recorded_purchase_comparison:PurchaseComparison|null;
  verified_purchase_comparison:PurchaseComparison|null;
  pending_purchase_comparison:PurchaseComparison|null;
  duplicate_serial_numbers:string[];
  outstanding_invoice_reviews:number;
  recorded_equipment_reconciled:boolean;
  verified_equipment_reconciled:boolean;
  warnings:string[];
};

const OCR_GROUPS=[
  '0O',
  '1IL',
  '2Z',
  '5S',
  '6G',
  '8B',
];

function possibleOcrMatch(
  observed:string,
  approved:string
){

  const left=observed.toUpperCase();
  const right=approved.toUpperCase();

  if(left===right||left.length!==right.length){
    return false;
  }

  let differences=0;

  for(let index=0;index<left.length;index++){

    if(left[index]===right[index])continue;

    differences++;

    if(differences>2)return false;

    if(!OCR_GROUPS.some(group=>
      group.includes(left[index])&&
      group.includes(right[index])
    )){
      return false;
    }
  }

  return differences>0;
}

export function EquipmentModelHint6026({
  model,
  reconciliation,
}:{
  model:string;
  reconciliation?:ProjectEquipmentReconciliation6026;
}){

  if(!model.trim()){

    return (
      <small className="equipment-hint-6026 warning">
        Enter the model number.
      </small>
    );
  }

  if(!reconciliation?.approved_requirements_available){

    return (
      <small className="equipment-hint-6026">
        Approved equipment comparison unavailable.
      </small>
    );
  }

  const expected=Array.from(new Set(
    reconciliation.required_equipment.map(
      row=>row.model_number
    )
  ));

  const normalized=model.trim().toLowerCase();

  const exact=expected.some(
    item=>item.toLowerCase()===normalized
  );

  if(exact){

    return (
      <small className="equipment-hint-6026 matched">
        Model matches approved MSR.
      </small>
    );
  }

  const possible=expected.filter(
    item=>possibleOcrMatch(model.trim(),item)
  );

  if(possible.length===1){

    return (
      <small className="equipment-hint-6026 warning">
        Possible reading error. Approved model:
        {' '}{possible[0]}.
        Check the original invoice.
      </small>
    );
  }

  if(possible.length>1){

    return (
      <small className="equipment-hint-6026 warning">
        More than one possible approved model.
        Check the original invoice.
      </small>
    );
  }

  return (
    <small className="equipment-hint-6026 warning">
      This model is not listed as a required purchase
      in the approved MSR.
    </small>
  );
}

function statusLabel(status:string){

  const labels:Record<string,string>={
    VERIFIED_PURCHASE_IDENTIFIERS_RECONCILED:
      'Required purchase identifiers match verified invoices.',
    PURCHASE_VERIFICATION_OUTSTANDING:
      'Recorded equipment matches. Purchase verification outstanding.',
    PURCHASE_QUANTITIES_OUTSTANDING:
      'Equipment purchase quantities require review.',
    EQUIPMENT_REVIEW_REQUIRED:
      'Equipment model or quantity differences require review.',
    DUPLICATE_SERIAL_REVIEW_REQUIRED:
      'Duplicate serial numbers require review.',
    INVOICE_REVIEW_REQUIRED:
      'One or more invoice records require review.',
    NO_APPROVED_EQUIPMENT_PURCHASE_REQUIRED:
      'No new equipment purchases are listed on this approved MSR.',
    APPROVED_REQUIREMENTS_UNAVAILABLE:
      'Approved equipment requirements are unavailable.',
    REVIEW_REQUIRED:
      'Equipment comparison requires review.',
  };

  return labels[status]||
    'Equipment comparison requires review.';
}

export default function DistributorEquipmentComparison6026({
  reconciliation,
}:{
  reconciliation?:ProjectEquipmentReconciliation6026;
}){

  if(!reconciliation){

    return (
      <div className="equipment-comparison-6026">
        <h3>Equipment purchase requirements</h3>
        <p>
          Equipment comparison is unavailable.
          Refresh after the backend update.
        </p>
      </div>
    );
  }

  const recorded=
    reconciliation.recorded_purchase_comparison;

  const verified=
    reconciliation.verified_purchase_comparison;

  const verifiedRows=new Map(
    (verified?.approved_equipment||[]).map(row=>[
      row.approved_model_number.trim().toLowerCase(),
      row.recorded_purchase_quantity,
    ])
  );

  const recordedRows=recorded?.approved_equipment||[];

  const unresolved=(
    recorded?.purchased_equipment||[]
  ).filter(row=>row.status!=='EXACT_MATCH');

  return (
    <section className="equipment-comparison-6026">

      <h3>Equipment purchase requirements</h3>

      {reconciliation.approved_requirements_available?(
        <>
          {reconciliation.required_equipment.length>0&&(
            <>
              <div className="equipment-totals-6026">

                <div>
                  <small>Required</small>
                  <strong>
                    {recorded?.approved_unit_count??0}
                  </strong>
                </div>

                <div>
                  <small>Recorded</small>
                  <strong>
                    {recorded?.exactly_matched_purchase_unit_count??0}
                  </strong>
                </div>

                <div>
                  <small>Verified</small>
                  <strong>
                    {verified?.exactly_matched_purchase_unit_count??0}
                  </strong>
                </div>

              </div>

              <div style={{overflowX:'auto'}}>
                <table className="equipment-comparison-table-6026">
                  <thead>
                    <tr>
                      <th>Model number</th>
                      <th>Required</th>
                      <th>Recorded</th>
                      <th>Verified</th>
                    </tr>
                  </thead>

                  <tbody>
                    {recordedRows.map(row=>{

                      const verifiedQuantity=verifiedRows.get(
                        row.approved_model_number
                          .trim().toLowerCase()
                      )||0;

                      return (
                        <tr key={row.approved_model_number}>

                          <td>
                            {row.approved_model_number}

                            {row.remaining_quantity>0&&
                              <small
                                className="equipment-hint-6026">
                                {row.remaining_quantity}
                                {' '}still to be recorded
                              </small>}

                            {row.excess_quantity>0&&
                              <small
                                className="equipment-hint-6026 warning">
                                {row.excess_quantity}
                                {' '}above approved quantity
                              </small>}

                          </td>

                          <td>{row.approved_quantity}</td>

                          <td>{row.recorded_purchase_quantity}</td>

                          <td>
                            {verifiedQuantity}
                          </td>

                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {unresolved.length>0&&
            <div className="equipment-review-6026">

              <strong>
                Purchased equipment requiring review
              </strong>

              {unresolved.map((row,index)=>
                <div key={index}>

                  <b>{row.observed_model_number}</b>

                  {' '}(Quantity: {row.quantity})

                  <EquipmentModelHint6026
                    model={row.observed_model_number}
                    reconciliation={reconciliation}/>

                </div>
              )}

            </div>}

          {reconciliation.existing_equipment.length>0&&
            <details className="equipment-existing-6026">

              <summary>
                Existing equipment receiving service or repair
              </summary>

              {reconciliation.existing_equipment.map(
                (row,index)=>
                  <p key={index}>
                    {row.model_number}
                    {' '}(Quantity: {row.quantity})
                  </p>
              )}

              <p>
                This equipment is not counted as a
                required new purchase.
              </p>

            </details>}

        </>
      ):(
        <p className="equipment-hint-6026 warning">
          The approved MSR equipment requirements
          could not be compared. Review the approved
          project information.
        </p>
      )}

      <p className={
        reconciliation.verified_equipment_reconciled
          ?'equipment-status-6026 matched'
          :'equipment-status-6026'
      }>
        {statusLabel(reconciliation.status)}
      </p>

      {reconciliation.duplicate_serial_numbers.length>0&&
        <p className="equipment-hint-6026 warning">
          Duplicate serial numbers:
          {' '}
          {reconciliation.duplicate_serial_numbers.join(', ')}
        </p>}

      {reconciliation.outstanding_invoice_reviews>0&&
        <p>
          Invoice records requiring additional review:
          {' '}
          {reconciliation.outstanding_invoice_reviews}
        </p>}

      {reconciliation.warnings.length>0&&
        <details className="equipment-existing-6026">

          <summary>Additional information</summary>

          {reconciliation.warnings.map((warning,index)=>
            <p key={index}>{warning}</p>
          )}

        </details>}

      <small className="muted">
        Purchase comparison only.
        Physical installation is confirmed separately.
      </small>

    </section>
  );
}
