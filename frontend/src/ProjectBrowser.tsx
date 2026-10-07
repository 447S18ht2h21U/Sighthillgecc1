import { useEffect, useState } from 'react';

type API=<T>(path:string,method?:string,data?:unknown)=>Promise<T>;
type Page<T>={count:number;next:string|null;previous:string|null;results:T[]};
type ProjectRow={id:string;code:string;location:string;state:string};
export function ProjectBrowser<T extends ProjectRow>({api,selectedId,refreshKey,onChoose}:{api:API;selectedId?:string;refreshKey:number;onChoose:(project:T)=>void}){
 const [query,setQuery]=useState(''),[state,setState]=useState(''),[sort,setSort]=useState('NEWEST'),[page,setPage]=useState(1);
 const [filters,setFilters]=useState({search:'',state:'',sort:'NEWEST'}),[results,setResults]=useState<Page<T>|null>(null),[error,setError]=useState('');
 useEffect(()=>{let closed=false;setResults(null);setError('');const params=new URLSearchParams({...filters,page:String(page)});api<Page<T>>(`projects/?${params}`).then(d=>{if(!closed)setResults(d);}).catch(e=>{if(!closed)setError(e.message);});return()=>{closed=true;};},[filters,page,refreshKey,api]);
 return <aside aria-label="Project list"><h2>Projects</h2><form className="record-filters" onSubmit={e=>{e.preventDefault();setPage(1);setFilters({search:query.trim(),state,sort});}}>
  <label>Search projects<input type="search" value={query} maxLength={200} onChange={e=>setQuery(e.target.value)} placeholder="Code, location or customer"/></label>
  <label>Project status<select aria-label="Project status" value={state} onChange={e=>setState(e.target.value)}><option value="">All statuses</option>{['DRAFT','SUBMITTED','APPROVED','REJECTED','REVISED','CANCELLED'].map(s=><option key={s} value={s}>{s[0]+s.slice(1).toLowerCase()}</option>)}</select></label>
  <label>Project order<select aria-label="Project order" value={sort} onChange={e=>setSort(e.target.value)}><option value="NEWEST">Newest first</option><option value="OLDEST">Oldest first</option><option value="CODE">Project code</option></select></label>
  <div className="actions"><button>Search projects</button><button type="button" className="quiet" onClick={()=>{setQuery('');setState('');setSort('NEWEST');setPage(1);setFilters({search:'',state:'',sort:'NEWEST'});}}>Clear project filters</button></div>
 </form><p className="muted">Search the customer record and names recorded in the current approved or pending MSR. Select Search projects to apply filters. Filters change the list; your open project remains available.</p>
 {error&&<p role="alert" className="error">{error}</p>}{results?<><p role="status">{results.count} projects found · Page {page}</p>{results.count===0&&<p>No projects match these filters.</p>}{results.results.map(p=><button className={`project ${selectedId===p.id?'active':''}`} key={p.id} onClick={()=>onChoose(p)}><strong>{p.code}</strong><span>{p.location}</span><span className="badge">{p.state}</span></button>)}<div className="actions"><button className="quiet" disabled={!results.previous} onClick={()=>setPage(n=>n-1)}>Previous projects</button><button className="quiet" disabled={!results.next} onClick={()=>setPage(n=>n+1)}>Next projects</button></div></>:!error&&<p>Loading projects…</p>}
 </aside>;
}
