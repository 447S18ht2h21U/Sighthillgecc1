import { useEffect, useState } from 'react';

type API = <T>(path:string, method?:string, data?:unknown)=>Promise<T>;
type Account = {id:string;username:string;first_name:string;last_name:string;email:string;initials:string;role:string;is_active:boolean;revision:string};
type Page = {count:number;next:string|null;previous:string|null;results:Account[]};
const roles = [
 ['SALES_ASSOCIATE','Sales Associate'],['SALES_MANAGER','Sales Manager'],['COMPTROLLER','Comptroller'],
 ['INSTALLATION_MANAGER','Installation Manager'],['TECHNICIAN','Technician'],
 ['ACCOUNTS_PAYABLE_ASSOCIATE','Accounts Payable Associate'],['DATABASE_ADMINISTRATOR','Database Administrator'],
];

export function AccountManagement({actorId,api,onChanged,onBack}:{actorId:string;api:API;onChanged:()=>Promise<void>;onBack:()=>void}) {
 const [data,setData]=useState<Page|null>(null),[page,setPage]=useState(1),[edit,setEdit]=useState<Account|null>(null);
 const [creating,setCreating]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 useEffect(()=>{let closed=false;setData(null);setError('');api<Page>(`accounts/?page=${page}`).then(d=>{if(!closed)setData(d);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[api,page]);
 async function refresh(){setData(await api<Page>(`accounts/?page=${page}`));}
 async function run(job:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await job();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 const self=edit?.id===actorId;
 return <section className="account-management" aria-labelledby="account-heading">
  <div className="title"><div><h2 id="account-heading">User management</h2><p className="muted">The Comptroller manages local GECC accounts. Changes require a note and are recorded in the audit history. Creating an account sends no email.</p></div><button className="quiet" disabled={busy} onClick={onBack}>Back to projects</button></div>
  {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status">{message}</p>}
  <div className="actions"><button disabled={busy} onClick={()=>{setEdit(null);setCreating(true);setError('');setMessage('');}}>Add user</button><button className="quiet" disabled={busy} onClick={()=>void run(refresh)}>Refresh users</button></div>
  {data?<><p>{data.count} users · Page {page}</p><ul className="account-list">{data.results.map(a=><li key={a.id}><div><strong>{a.first_name} {a.last_name}</strong><span>{a.username} · {a.email||'Email not set'}</span><span>{roles.find(r=>r[0]===a.role)?.[1]||a.role} · {a.is_active?'Active':'Inactive'}{a.id===actorId?' · Your account':''}</span></div><button className="quiet" disabled={busy} aria-label={`Edit user ${a.username}`} onClick={()=>{setEdit(a);setCreating(false);setError('');setMessage('');}}>Edit user</button></li>)}</ul><div className="actions"><button className="quiet" disabled={busy||!data.previous} onClick={()=>{setPage(p=>p-1);setEdit(null);setCreating(false);}}>Previous users</button><button className="quiet" disabled={busy||!data.next} onClick={()=>{setPage(p=>p+1);setEdit(null);setCreating(false);}}>Next users</button></div></>:<p>Loading users…</p>}
  {(creating||edit)&&<form key={edit?.revision||'new'} onSubmit={e=>{
   e.preventDefault();const form=e.currentTarget,f=Object.fromEntries(new FormData(form));
   const payload:{[key:string]:unknown}={...f};
   if(self){delete payload.role;delete payload.is_active;}else payload.is_active=f.is_active==='on';
   if(edit){payload.expected_revision=edit.revision;if(!f.password)delete payload.password;}
   void run(async()=>{await api(edit?`accounts/${edit.id}/`:'accounts/',edit?'PATCH':'POST',payload);form.reset();setEdit(null);setCreating(false);await refresh();await onChanged();setMessage(edit?'User changes saved.':'User created.');});
  }}>
   <h3>{edit?`Edit user: ${edit.username}`:'New user'}</h3>
   <fieldset disabled={busy}><div className="grid">
    {!edit&&<label>Username<input name="username" required maxLength={150} autoComplete="off"/></label>}
    <label>User first name<input name="first_name" defaultValue={edit?.first_name||''} required maxLength={150}/></label>
    <label>User last name<input name="last_name" defaultValue={edit?.last_name||''} required maxLength={150}/></label>
    <label>User email<input type="email" name="email" defaultValue={edit?.email||''} required maxLength={254}/></label>
    <label>User initials<input aria-label="User initials" name="initials" defaultValue={edit?.initials||''} required pattern="[A-Z]{1,8}" maxLength={8}/><span className="muted">Use 1–8 uppercase letters.</span></label>
    <label>User role<select aria-label="User role" name="role" disabled={self} defaultValue={edit?.role||'SALES_ASSOCIATE'}>{roles.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    {!self&&<label>{edit?'New local password (optional)':'Local password'}<input aria-label={edit?'New local password (optional)':'Local password'} name="password" type="password" required={!edit} minLength={12} autoComplete="new-password"/><span className="muted">At least 12 characters, including a letter, number and special character.{edit?' Leave blank to keep the existing password.':''}</span></label>}
   </div>
   <label className="sandbox-confirm"><input type="checkbox" name="is_active" disabled={self} defaultChecked={edit?edit.is_active:true}/>Account active — can sign in</label>
   {self&&<p>Your own role and active status cannot be changed here.</p>}
   <label>Account change note<textarea name="change_note" required maxLength={2000}/></label>
   <p className="muted">Deactivation blocks sign-in and future business actions. Existing project records, approvals and document history are retained. Reviewers and signers must remain authorized; account changes can block pending document packages.</p>
   <div className="actions"><button>{edit?'Save user changes':'Create user'}</button><button type="button" className="quiet" onClick={()=>{setEdit(null);setCreating(false);setError('');}}>Cancel user changes</button></div>
   </fieldset>
  </form>}
 </section>;
}
