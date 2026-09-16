import React,{useState,useEffect,useCallback}from'react';
import TimetableGrid from '../../components/timetable/TimetableGrid';
import api from '../../services/api';
import {getApiErrorMessage} from '../../services/apiError';
import '../../styles/TimetableGrid.css';

export default function MyTimetable(){
 const[terms,setTerms]=useState([]),[selectedTerm,setSelectedTerm]=useState(''),[periods,setPeriods]=useState([]),[entries,setEntries]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let active=true;api.get('/api/terms/').then(({data})=>{if(!active)return;const list=data.results??data;setTerms(list);const current=list.find(t=>t.is_current);if(current)setSelectedTerm(String(current.id));}).catch(err=>active&&setError(getApiErrorMessage(err,'Unable to load school terms.')));return()=>{active=false;};},[]);
 const loadData=useCallback(async()=>{if(!selectedTerm)return;setLoading(true);setError('');try{const[p,e]=await Promise.all([api.get('/api/timetable/periods/'),api.get(`/api/timetable/entries/my-timetable/?term=${selectedTerm}`)]);setPeriods(p.data.results??p.data);setEntries(e.data.results??e.data);}catch(err){setPeriods([]);setEntries([]);setError(getApiErrorMessage(err,'Unable to load your timetable.'));}finally{setLoading(false);}},[selectedTerm]);
 useEffect(()=>{loadData();},[loadData]); useEffect(()=>{const id=setInterval(loadData,60000);return()=>clearInterval(id);},[loadData]);
 return <div className="tt-page"><div className="tt-toolbar"><h1 className="tt-toolbar__title">My Timetable<small>Your assigned lessons for the week</small></h1><div className="tt-selector-group"><label>Term</label><select className="tt-select" value={selectedTerm} onChange={e=>setSelectedTerm(e.target.value)}>{terms.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></div></div>{error?<div className="tt-grid-wrap"><div className="tt-empty-state" role="alert"><strong>Unable to open timetable</strong>{error}</div></div>:<><TimetableGrid periods={periods} entries={entries} editable={false} highlightCurrent loading={loading}/><p style={{fontSize:'.74rem',color:'var(--ink-muted)',marginTop:14,fontFamily:'var(--font-mono)'}}>● Green outline = current period — refreshes automatically every minute</p></>}</div>;
}
