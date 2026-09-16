import React, { useState, useEffect, useCallback, useContext } from 'react';
import TimetableGrid, { TimetableLegend } from '../../components/timetable/TimetableGrid';
import api from '../../services/api';
import { getApiErrorMessage } from '../../services/apiError';
import { AuthContext } from '../../context/AuthContext';
import '../../styles/TimetableGrid.css';

export default function StudentTimetable() {
  const { user } = useContext(AuthContext);
  const classArmId = user?.class_arm_id ?? null;
  const [terms,setTerms]=useState([]), [selectedTerm,setSelectedTerm]=useState(''), [periods,setPeriods]=useState([]), [entries,setEntries]=useState([]);
  const [loading,setLoading]=useState(false), [error,setError]=useState('');

  useEffect(()=>{let active=true; api.get('/api/terms/').then(({data})=>{if(!active)return;const list=data.results??data;setTerms(list);const current=list.find(t=>t.is_current);if(current)setSelectedTerm(String(current.id));}).catch(err=>active&&setError(getApiErrorMessage(err,'Unable to load school terms.')));return()=>{active=false;};},[]);

  const loadData=useCallback(async()=>{if(!selectedTerm||!classArmId)return;setLoading(true);setError('');try{const[pRes,eRes]=await Promise.all([api.get('/api/timetable/periods/'),api.get(`/api/timetable/entries/by-class/${classArmId}/?term=${selectedTerm}`)]);setPeriods(pRes.data.results??pRes.data);setEntries(eRes.data.results??eRes.data);}catch(err){setPeriods([]);setEntries([]);setError(getApiErrorMessage(err,'Unable to load your timetable.'));}finally{setLoading(false);}},[selectedTerm,classArmId]);
  useEffect(()=>{loadData();},[loadData]);

  if(!classArmId)return <div className="tt-page"><div className="tt-grid-wrap"><div className="tt-empty-state"><strong>No class assigned</strong>Your class placement hasn't been recorded yet. Please contact your school administrator.</div></div></div>;

  return <div className="tt-page"><div className="tt-toolbar"><h1 className="tt-toolbar__title">Class Timetable<small>Your weekly lesson schedule</small></h1><div className="tt-selector-group"><label>Term</label><select className="tt-select" value={selectedTerm} onChange={e=>setSelectedTerm(e.target.value)}>{terms.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></div></div>
    {error?<div className="tt-grid-wrap"><div className="tt-empty-state" role="alert"><strong>Unable to open timetable</strong>{error}</div></div>:<><TimetableGrid periods={periods} entries={entries} editable={false} highlightCurrent={false} loading={loading}/><TimetableLegend/></>}
  </div>;
}
