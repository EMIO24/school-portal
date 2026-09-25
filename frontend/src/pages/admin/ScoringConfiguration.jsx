import React, {useEffect, useState} from 'react';
import api from '../../services/api';

export function scoringError(error) {
  const flatten = value => typeof value === 'string' ? value : Array.isArray(value) ? value.map(flatten).join(' ') : value && typeof value === 'object' ? Object.entries(value).map(([key,v]) => `${key}: ${flatten(v)}`).join(' ') : '';
  return flatten(error.response?.data) || 'Could not save. Check your connection and try again.';
}

export default function ScoringConfiguration({onSaved}) {
  const [terms,setTerms]=useState([]), [term,setTerm]=useState(''), [config,setConfig]=useState(null);
  const [busy,setBusy]=useState(false), [error,setError]=useState(''), [notice,setNotice]=useState('');
  useEffect(() => {api.get('/api/terms/').then(r => setTerms(r.data.results ?? r.data)).catch(e => setError(scoringError(e)));},[]);
  useEffect(() => {
    let active=true; setConfig(null); setError(''); setNotice('');
    if(term) api.get(`/api/gradebook/configuration/?term=${term}`).then(r => {if(active)setConfig(r.data);}).catch(e => {if(active)setError(scoringError(e));});
    return () => {active=false;};
  },[term]);
  const change=(kind,index,key,value) => setConfig({...config,[kind]:config[kind].map((row,i) => i===index ? {...row,[key]:value} : row)});
  async function save(e) {
    e.preventDefault();setBusy(true);setError('');setNotice('');
    try {const r=await api.put(`/api/gradebook/configuration/?term=${term}`,config);setConfig(r.data);setNotice('Assessment and grading saved.');onSaved?.();}
    catch(err){setError(scoringError(err));}finally{setBusy(false);}
  }
  return <section id="assessment"><h2>Assessment and grading</h2>
    <p>Choose a term, name each assessment and allocate a total of 100 marks. Once scores exist, use a future term to change the rules.</p>
    <label>Assessment term<select value={term} onChange={e=>setTerm(e.target.value)}><option value="">Choose a term</option>{terms.map(t=><option key={t.id} value={t.id}>{t.name} — {t.session_name || t.session}</option>)}</select></label>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {config && <form onSubmit={save}><fieldset disabled={busy || config.locked}>
      {config.locked && <p>This term has scores. Its assessment and grading rules are protected.</p>}
      <h3>Assessment components</h3>
      {config.components.map((c,i)=><div className="setup-fields" key={c.key}>
        <label>Assessment name<input required value={c.name} onChange={e=>change('components',i,'name',e.target.value)}/></label>
        <label>Maximum score<input required type="number" min="0.01" max="100" step="0.01" value={c.maximum} onChange={e=>change('components',i,'maximum',e.target.value)}/></label>
        <label>Type<select value={c.kind} onChange={e=>change('components',i,'kind',e.target.value)}><option value="assessment">Assessment</option><option value="exam">Examination</option></select></label>
        <button type="button" onClick={()=>setConfig({...config,components:config.components.filter((_,n)=>n!==i)})}>Remove assessment</button>
      </div>)}
      <button type="button" onClick={()=>{const keys=new Set(config.components.map(c=>c.key));let n=1;while(keys.has(`component_${n}`))n++;setConfig({...config,components:[...config.components,{key:`component_${n}`,name:'',maximum:'',kind:'assessment'}]});}}>Add assessment</button>
      <h3>Grading ranges</h3><p>Cover every score from 0 to 100. For example, one range ends at 69.99 and the next begins at 70.</p>
      {config.bands.map((b,i)=><div className="setup-fields" key={i}>{[['grade','Grade'],['min_score','Minimum score'],['max_score','Maximum score'],['remark','Remark']].map(([key,label])=><label key={key}>{label}<input required type={key.includes('score')?'number':'text'} step="0.01" value={b[key]} onChange={e=>change('bands',i,key,e.target.value)}/></label>)}<button type="button" onClick={()=>setConfig({...config,bands:config.bands.filter((_,n)=>n!==i)})}>Remove grade</button></div>)}
      <button type="button" onClick={()=>setConfig({...config,bands:[...config.bands,{grade:'',min_score:'',max_score:'',remark:''}]})}>Add grade</button>
      <button type="submit">Save assessment and grading</button>
    </fieldset></form>}
  </section>;
}
