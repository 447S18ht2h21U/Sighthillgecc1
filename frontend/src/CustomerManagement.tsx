import { useEffect, useState } from 'react';

type API=<T>(path:string,method?:string,data?:unknown)=>Promise<T>;
type Customer={id:string;legal_name:string;billing_address:string;email:string;phone:string;archived:boolean;revision:string;primary_contact:{id:string;name:string}|null};
type Contact={id:string;customer:string;name:string;relationship:string;email:string;phone:string;primary:boolean;revision:string};
type Page<T>={count:number;next:string|null;previous:string|null;results:T[]};

export function CustomerManagement({api,onChanged,onBack}:{api:API;onChanged:()=>Promise<void>;onBack:()=>void}){
 const [customers,setCustomers]=useState<Page<Customer>|null>(null),[page,setPage]=useState(1),[selected,setSelected]=useState<Customer|null>(null);
 const [contacts,setContacts]=useState<Page<Contact>|null>(null),[contactPage,setContactPage]=useState(1);
 const [editCustomer,setEditCustomer]=useState(false),[editContact,setEditContact]=useState<Contact|null>(null),[newContact,setNewContact]=useState(false),[primary,setPrimary]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 useEffect(()=>{let closed=false;setCustomers(null);api<Page<Customer>>(`customers/?page=${page}`).then(d=>{if(!closed)setCustomers(d);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[page,api]);
 useEffect(()=>{let closed=false;setContacts(null);if(selected)api<Page<Contact>>(`contacts/?customer=${selected.id}&page=${contactPage}`).then(d=>{if(!closed)setContacts(d);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[selected?.id,contactPage,api]);
 async function run(job:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await job();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function refresh(){setCustomers(await api<Page<Customer>>(`customers/?page=${page}`));if(selected){setSelected(await api<Customer>(`customers/${selected.id}/`));setContacts(await api<Page<Contact>>(`contacts/?customer=${selected.id}&page=${contactPage}`));}}
 function closeForms(){setEditCustomer(false);setEditContact(null);setNewContact(false);}
 const replacing=primary&&selected?.primary_contact&&selected.primary_contact.id!==editContact?.id;
 return <section className="customer-management" aria-labelledby="customer-record-heading">
  <div className="title"><div><h2 id="customer-record-heading">Customer records</h2><p className="muted">Manage the customers you are authorized to access and their contacts. Approved project versions and existing documents keep their recorded details.</p></div><button className="quiet" disabled={busy} onClick={onBack}>Back to projects</button></div>
  {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
  <button className="quiet" disabled={busy} onClick={()=>void run(refresh)}>Refresh customer records</button>
  <div className="customer-layout"><div>
   {customers?<><p>{customers.count} customers · Page {page}</p><ul className="customer-record-list">{customers.results.map(c=><li key={c.id}><strong>{c.legal_name}</strong><p>{c.billing_address}</p><span>{c.archived?'Archived':'Active'}</span><button className="quiet" aria-label={`Open customer ${c.legal_name}`} disabled={busy} onClick={()=>void run(async()=>{setSelected(await api<Customer>(`customers/${c.id}/`));setContactPage(1);closeForms();})}>Open customer</button></li>)}</ul><div className="actions"><button className="quiet" disabled={busy||!customers.previous} onClick={()=>{setPage(p=>p-1);setSelected(null);closeForms();}}>Previous customers</button><button className="quiet" disabled={busy||!customers.next} onClick={()=>{setPage(p=>p+1);setSelected(null);closeForms();}}>Next customers</button></div></>:<p>Loading customers…</p>}
  </div><div>{selected?<>
   <h3>{selected.legal_name}</h3><p className="customer-address">{selected.billing_address}</p><p>{selected.email||'Email not set'}<br/>{selected.phone||'Phone not set'}</p><p>{selected.archived?'Archived — unavailable for new projects':'Active customer'}</p><p>Primary contact: {selected.primary_contact?.name||'None selected'}</p>
   <button className="quiet" disabled={busy} onClick={()=>{closeForms();setEditCustomer(true);setError('');setMessage('');}}>Edit customer</button>
   {editCustomer&&<form key={selected.revision} onSubmit={e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.currentTarget));void run(async()=>{await api(`customers/${selected.id}/`,'PATCH',{...f,archived:f.archived==='on',expected_revision:selected.revision});setEditCustomer(false);await refresh();await onChanged();setMessage('Customer changes saved.');});}}>
    <h3>Edit customer details</h3><fieldset disabled={busy}><div className="grid">
     <label>Customer legal name<input name="legal_name" defaultValue={selected.legal_name} required maxLength={250}/></label>
     <label>Customer billing address<textarea aria-label="Customer billing address" name="billing_address" defaultValue={selected.billing_address} required/></label>
     <label>Customer email<input name="email" type="email" defaultValue={selected.email} maxLength={254}/></label>
     <label>Customer phone<input name="phone" defaultValue={selected.phone} maxLength={40}/></label>
    </div><label className="sandbox-confirm"><input name="archived" type="checkbox" defaultChecked={selected.archived}/>Customer archived — unavailable for new projects</label>
    <label>Customer change note<textarea aria-label="Customer change note" name="change_note" required maxLength={2000}/></label>
    <label>Duplicate override reason (only if warned)<textarea aria-label="Duplicate override reason (only if warned)" name="duplicate_reason" maxLength={2000}/></label>
    <p className="muted">These changes update the customer record. Existing project snapshots stay unchanged. Revise an approved Master Sales Record separately when commercial details need to change.</p>
    <div className="actions"><button>Save customer changes</button><button type="button" className="quiet" onClick={closeForms}>Cancel customer changes</button></div></fieldset>
   </form>}
   <h3>Customer contacts</h3><button className="quiet" disabled={busy||selected.archived} onClick={()=>{closeForms();setNewContact(true);setPrimary(!selected.primary_contact);setError('');setMessage('');}}>Add contact</button>
   {contacts?<><p>{contacts.count} contacts · Page {contactPage}</p><ul className="contact-list">{contacts.results.map(c=><li key={c.id}><strong>{c.name}{c.primary?' · Primary contact':''}</strong><p>{c.relationship||'Relationship not set'}<br/>{c.email||'Email not set'}<br/>{c.phone||'Phone not set'}</p><button className="quiet" disabled={busy} aria-label={`Edit contact ${c.name}`} onClick={()=>{closeForms();setEditContact(c);setPrimary(c.primary);setError('');setMessage('');}}>Edit contact</button></li>)}</ul><div className="actions"><button className="quiet" disabled={busy||!contacts.previous} onClick={()=>{setContactPage(p=>p-1);closeForms();}}>Previous contacts</button><button className="quiet" disabled={busy||!contacts.next} onClick={()=>{setContactPage(p=>p+1);closeForms();}}>Next contacts</button></div></>:<p>Loading contacts…</p>}
   {(newContact||editContact)&&<form key={editContact?.revision||`new-${selected.id}`} onSubmit={e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.currentTarget));void run(async()=>{await api(editContact?`contacts/${editContact.id}/`:'contacts/',editContact?'PATCH':'POST',{...f,...(editContact?{expected_revision:editContact.revision}:{customer:selected.id}),primary,replace_primary_confirmed:f.replace_primary_confirmed==='on',expected_primary_id:selected.primary_contact?.id||''});closeForms();await refresh();setMessage(editContact?'Contact changes saved.':'Contact created.');});}}>
    <h3>{editContact?'Edit contact details':'New contact'}</h3><fieldset disabled={busy}><div className="grid">
     <label>Contact name<input name="name" defaultValue={editContact?.name||''} required maxLength={250}/></label>
     <label>Contact relationship<input name="relationship" defaultValue={editContact?.relationship||''} maxLength={100}/></label>
     <label>Contact email<input name="email" type="email" defaultValue={editContact?.email||''} maxLength={254}/></label>
     <label>Contact phone<input name="phone" defaultValue={editContact?.phone||''} maxLength={40}/></label>
    </div><label className="sandbox-confirm"><input type="checkbox" checked={primary} onChange={e=>setPrimary(e.target.checked)}/>Primary contact for this customer</label>
    {replacing&&<label className="sandbox-confirm"><input type="checkbox" name="replace_primary_confirmed" required/>Replace {selected.primary_contact?.name} as primary contact. Keep their contact record.</label>}
    <label>Contact change note<textarea aria-label="Contact change note" name="change_note" required maxLength={2000}/></label>
    <div className="actions"><button>{editContact?'Save contact changes':'Create contact'}</button><button type="button" className="quiet" onClick={closeForms}>Cancel contact changes</button></div></fieldset>
   </form>}
  </>:<p>Select a customer to edit details and manage contacts.</p>}</div></div>
 </section>;
}
