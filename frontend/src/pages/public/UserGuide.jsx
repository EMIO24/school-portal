import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import guides from '../../content/userGuides.json';
import { downloadReport } from '../../services/pdf';
import './UserGuide.css';
export default function UserGuide({ allowDownloads = false }) {
  const {user}=useAuth();
  const canDownload = allowDownloads && user?.role === 'superadmin';
  const visibleGuides = guides.filter(g => g.id !== 'superadmin' || canDownload);
  const [selected,setSelected]=useState(user?.role==='teacher'?'staff':user?.role || 'start');
  const [error,setError]=useState('');
  const guide=visibleGuides.find(g=>g.id===selected) || visibleGuides[0];
  function download(all=false) {
    if (!canDownload) return;
    try {const items=all?guides:[guides[0],guide,...(guide.id==='help'?[]:[guides[guides.length-1]])].filter((g,i,a)=>a.findIndex(x=>x.id===g.id)===i);
      downloadReport(all?'School portal user guide':guide.title+' guide',items.flatMap(g=>[g.title,g.intro,'',...g.sections.flatMap(s=>[s.title,...s.steps.map((step,i)=>(i+1)+'. '+step),''])]),all?'school-portal-user-guide.pdf':guide.id+'-user-guide.pdf');
    } catch {setError('The PDF could not be created. You can still read the guide here or use your browser print option.');}
  }
  return <main className="user-guide"><header><span className="workspace-eyebrow">HELP FOR EVERY ROLE</span><h1>Your guide to the school portal</h1><p>Choose your role for step-by-step help. All five portal designs use the same features and page names.</p></header>
    <div className="guide-tools"><label>Choose your guide<select value={guide.id} onChange={e=>{setSelected(e.target.value);setError('');}}>{visibleGuides.map(g=><option value={g.id} key={g.id}>{g.title}</option>)}</select></label>{canDownload && <><button onClick={()=>download(false)}>Download this guide (PDF)</button><button onClick={()=>download(true)}>Download all guides (PDF)</button></>}</div>
    {error&&<p role="alert">{error}</p>}<article aria-labelledby="guide-role-title"><h2 id="guide-role-title">{guide.title}</h2><p>{guide.intro}</p><nav aria-label="Guide contents"><strong>In this guide</strong><ol>{guide.sections.map((s,i)=><li key={s.title}><a href={'#guide-section-'+i}>{s.title}</a></li>)}</ol></nav>{guide.sections.map((s,i)=><section id={'guide-section-'+i} key={s.title}><h3>{s.title}</h3><ol>{s.steps.map(step=><li key={step}>{step}</li>)}</ol></section>)}</article>
  </main>;
}
