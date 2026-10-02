import React,{useEffect,useState} from 'react';
import api from '../../services/api';
import '../admin/AssessmentCentre.css';

export default function LearningResources(){
  const [items,setItems]=useState([]),[error,setError]=useState('');
  useEffect(()=>{api.get('/api/curriculum/student-resources/').then(({data})=>setItems(data.resources||[])).catch(e=>setError(e?.response?.data?.detail||'Could not load learning resources.'));},[]);
  return <main className="assessment-page"><header><h1>Learning resources</h1><p>Approved notes, handouts, slides and worksheets for your current class.</p></header>
    {error&&<p role="alert" className="assessment-error">{error}</p>}
    <section className="assessment-card">{!items.length&&<p>No approved learning resources are available yet.</p>}<div className="assessment-list">{items.map(r=><article key={r.id} className="assessment-submission"><strong>{r.subject_name} · {r.title}</strong><p>{r.kind} · revision {r.revision}</p>{r.content&&<p>{r.content}</p>}{r.external_url&&<a href={r.external_url} target="_blank" rel="noreferrer">Open resource</a>}</article>)}</div></section>
  </main>;
}
