import React, {useEffect,useState} from "react";
import api from '../../services/api';
import WorkspaceHome from "../../components/common/WorkspaceHome";
export default function TeacherDashboard(){
  const [data,setData]=useState(null),[page,setPage]=useState(1),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  useEffect(()=>{let active=true;setData(null);setError('');api.get(`/api/subject-assignments/?mine=true&page=${page}`).then(r=>{if(active)setData(r.data);}).catch(()=>{if(active)setError('Could not load your teaching assignments.');});return()=>{active=false;};},[page,retry]);
  const rows=data?.results ?? data ?? [];
  return <main className="page-shell"><WorkspaceHome/><section><h2>Your teaching assignments</h2>
    <p>Use Take attendance for your register and Enter scores to save drafts and submit results for review. Submitted results are locked until an administrator reopens them.</p>
    {error?<p role="alert">{error} <button onClick={()=>setRetry(r=>r+1)}>Retry</button></p>:!data?<p role="status">Loading assignments...</p>:rows.length?<><ul>{rows.map(a=><li key={a.id}>{a.class_arm_name} — {a.subject_name} ({a.term_name}, {a.session_name})</li>)}</ul><nav aria-label="Assignment pages"><button disabled={page===1} onClick={()=>setPage(p=>p-1)}>Previous</button><button disabled={!data.next} onClick={()=>setPage(p=>p+1)}>Next</button></nav></>:<p>No teaching assignments yet. Ask your school administrator to assign your class, subject and term.</p>}
  </section></main>;
}
