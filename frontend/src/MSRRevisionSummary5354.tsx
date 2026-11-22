type Version = {
  source?:string|null;
  revision_reason?:string|null;
  created_at?:string;
  created_by_name?:string;
  snapshot:unknown;
};
type Change = {label:string;before:string;after:string};
const labels:Record<string,string> = {
  customer:'Customer',
  contact:'Customer contact',
  project_location:'Installation address',
  billing_address:'Billing address',
  scope:'Scope of work',
  payment_option:'Payment arrangement',
  payment_terms:'Payment terms',
  financing_type:'Financing',
  commercial_notes:'Special customer arrangements / notes',
  marketing_promotion:'Marketing Promotion',
};

function obj(value:unknown):Record<string,unknown> {
  return value !== null && typeof value==='object' &&
    !Array.isArray(value) ? value as Record<string,unknown> : {};
}

function show(value:unknown):string {
  if (value===null || value===undefined || value==='') return 'Not recorded';
  if (typeof value==='string' || typeof value==='number') return String(value);
  if (typeof value==='boolean') return value?'Yes':'No';
  return JSON.stringify(value);
}

type MaterialComparison = {
  name:string;
  quantity:string;
  unit:string;
  confirmed:boolean;
  standard:boolean;
};

const standardUnits:Record<string,string> = {
  'ductwork':'linear feet',
  'electrical wiring':'linear feet',
  'refrigerant':'lb',
};

function materialMap(value:unknown):Map<string,MaterialComparison> {
  const map=new Map<string,MaterialComparison>();
  const counts=new Map<string,number>();
  if (!Array.isArray(value)) return map;

  for (const entry of value) {
    const row=obj(entry);
    const description=String(row.description??'Material').trim();
    const match=description.match(
      /^(ductwork|electrical wiring|refrigerant)(?:\s*\((linear feet|lb)\))?$/i
    );

    const name=match ? match[1].toLowerCase() : description.toLowerCase();
    const expectedUnit=standardUnits[name]??'';
    const confirmed=Boolean(
      match && match[2] &&
      match[2].toLowerCase()===expectedUnit
    );
    const occurrence=(counts.get(name)??0)+1;
    counts.set(name,occurrence);

    map.set(`${name}#${occurrence}`,{
      name:match ? match[1] : description,
      quantity:show(row.quantity),
      unit:expectedUnit,
      confirmed,
      standard:Boolean(match),
    });
  }
  return map;
}

function displayMaterial(value:MaterialComparison|undefined):string {
  if (!value) return 'Not included';
  if (!value.standard) return value.quantity;
  return value.confirmed
    ? `${value.quantity} ${value.unit} (confirmed)`
    : `${value.quantity} (unit not confirmed)`;
}

function describeChanges(beforeValue:unknown,afterValue:unknown):Change[] {
  const before=obj(beforeValue);
  const after=obj(afterValue);
  const result:Change[]=[];
  const oldMaterials=materialMap(before.materials);
  const newMaterials=materialMap(after.materials);

  for (const key of new Set([
    ...oldMaterials.keys(),
    ...newMaterials.keys()
  ])) {
    const old=oldMaterials.get(key);
    const next=newMaterials.get(key);

    if (
      old?.quantity!==next?.quantity ||
      old?.confirmed!==next?.confirmed ||
      old?.unit!==next?.unit
    ) {
      result.push({
        label:`Material: ${next?.name??old?.name??'Unknown'}`,
        before:displayMaterial(old),
        after:next ? displayMaterial(next) : 'Removed',
      });
    }
  }

  const oldEquipment=Array.isArray(before.equipment)?before.equipment:[];
  const newEquipment=Array.isArray(after.equipment)?after.equipment:[];
  for (let i=0;i<Math.max(oldEquipment.length,newEquipment.length);i++) {
    if (JSON.stringify(oldEquipment[i])!==JSON.stringify(newEquipment[i])) {
      result.push({
        label:`Equipment entry ${i+1}`,
        before:show(oldEquipment[i]??'Not included'),
        after:show(newEquipment[i]??'Removed')
      });
    }
  }
  for (const key of new Set([...Object.keys(before),...Object.keys(after)])) {
    if (key==='materials'||key==='equipment') continue;
    if (JSON.stringify(before[key])!==JSON.stringify(after[key])) {
      result.push({
        label:labels[key]??key.replaceAll('_',' '),
        before:show(before[key]),
        after:show(after[key])
      });
    }
  }
  return result;
}

export default function MSRRevisionSummary5354({
  version,sourceVersion
}:{
  version:Version;
  sourceVersion?:Version;
}) {
  if (!version.source) return null;
  const differences=sourceVersion
    ? describeChanges(sourceVersion.snapshot,version.snapshot):[];
  const date=version.created_at?new Date(version.created_at):null;
  const timestamp=date&&!Number.isNaN(date.getTime())
    ? date.toLocaleString():'Not available';

  return <section aria-label="What Changed" style={{
    background:'#fff',border:'1px solid #D7E3E7',
    borderRadius:8,padding:16,margin:'12px 0 18px'
  }}>
    <strong style={{fontSize:'1.1rem'}}>What Changed</strong>
    <p><strong>Changed by:</strong> {version.created_by_name||'Not available'}</p>
    <p><strong>When:</strong> {timestamp}</p>
    <p><strong>Reason:</strong> {version.revision_reason||'Not recorded'}</p>
    {!sourceVersion
      ? <p>Previous version unavailable for comparison.</p>
      : differences.length===0
      ? <p>No changes detected.</p>
      : <div style={{overflowX:'auto'}}>
        <table style={{width:'100%',borderCollapse:'collapse',textAlign:'left'}}>
          <thead><tr>
            <th style={{padding:8}}>Changed field</th>
            <th style={{padding:8}}>Previous</th>
            <th style={{padding:8}}>Revised</th>
          </tr></thead>
          <tbody>{differences.map((item,index)=><tr key={`${item.label}-${index}`}>
            <td style={{padding:8,verticalAlign:'top'}}>{item.label}</td>
            <td style={{padding:8,verticalAlign:'top',overflowWrap:'anywhere'}}>{item.before}</td>
            <td style={{padding:8,verticalAlign:'top',overflowWrap:'anywhere'}}>{item.after}</td>
          </tr>)}</tbody>
        </table>
      </div>}
  </section>;
}
