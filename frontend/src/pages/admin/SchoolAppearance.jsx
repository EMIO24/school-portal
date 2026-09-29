import React, { useEffect, useState } from 'react';
import api from '../../services/api';
import { useTheme } from '../../context/ThemeContext';
import { DESIGNS, DEFAULT_DESIGN } from '../../services/designPresets';
import { DesignPreview } from '../platform/PortalDesigns';
import '../platform/PortalDesigns.css';

const defaults = {layout:DEFAULT_DESIGN.id,primary_color:DEFAULT_DESIGN.colors[0],
  secondary_color:DEFAULT_DESIGN.colors[1],accent_color:DEFAULT_DESIGN.colors[2],font_family:DEFAULT_DESIGN.font};
function errorText(error) {
  const data = error.response?.data;
  return data?.detail || (data ? Object.entries(data).map(([key,value]) => `${key}: ${value}`).join(' ') : 'Could not save appearance. Check your connection and try again.');
}
export default function SchoolAppearance() {
  const { refetch } = useTheme();
  const [school,setSchool] = useState(null),[theme,setTheme] = useState(defaults);
  const [loading,setLoading] = useState(true),[busy,setBusy] = useState(false),[error,setError] = useState(''),[notice,setNotice] = useState('');
  useEffect(() => {api.get('/api/school/appearance/').then(({data}) => {
    setSchool(data);setTheme({...defaults,...data.theme});
  }).catch(e => setError(errorText(e))).finally(() => setLoading(false));}, []);
  const select = design => {setTheme({layout:design.id,primary_color:design.colors[0],
    secondary_color:design.colors[1],accent_color:design.colors[2],font_family:design.font});setNotice('');};
  async function save() {
    setBusy(true);setError('');setNotice('');
    try {
      const {layout,primary_color,secondary_color,accent_color,font_family} = theme;
      await api.patch('/api/school/appearance/',{theme_config:{layout,primary_color,secondary_color,accent_color,font_family}});
      await refetch();setNotice('Appearance saved for your school.');
    } catch (e) {setError(errorText(e));} finally {setBusy(false);}
  }
  return <main className="design-studio"><div className="design-page-heading"><div><span className="workspace-eyebrow">SCHOOL SETTINGS</span><h1>School appearance</h1><p>Choose a design, adjust your colours, preview, then save.</p></div><span className="design-count">10 <small>PORTAL DESIGNS</small></span></div>
    {error&&<p role="alert" className="design-error">{error}</p>}{notice&&<p role="status" className="design-notice">{notice}</p>}
    {loading?<p role="status">Loading appearance...</p>:school&&<>
      <fieldset disabled={busy} className="design-fieldset"><legend>01 / Choose a design</legend><div className="design-gallery">{DESIGNS.map(design=><button key={design.id} type="button" aria-label={design.name+' '+design.tag} aria-pressed={theme.layout===design.id} onClick={()=>select(design)} className={'design-option'+(theme.layout===design.id?' chosen':'')}>
        <DesignPreview layout={design.id} theme={{primary_color:design.colors[0],secondary_color:design.colors[1],accent_color:design.colors[2]}} name={school.name}/><div className="design-option-caption"><div><strong>{design.name}</strong><span>{design.tag}</span></div></div><p>{design.description}</p></button>)}</div></fieldset>
      <div className="design-edit-grid"><section className="design-controls"><fieldset disabled={busy} className="design-fieldset"><legend>02 / Refine colours</legend><p className="design-help">Your school name, motto and logo are managed in School setup.</p><div className="design-colors">{[['primary_color','Primary'],['secondary_color','Secondary'],['accent_color','Accent']].map(([key,label])=><label key={key}>{label}<input type="color" aria-label={label} value={theme[key]} onChange={e=>setTheme({...theme,[key]:e.target.value})}/><span>{theme[key]}</span></label>)}</div><label>Typography<select value={theme.font_family} onChange={e=>setTheme({...theme,font_family:e.target.value})}><option value="'Segoe UI', sans-serif">Modern / Segoe UI</option><option value="Arial, sans-serif">Clean / Arial</option><option value="Georgia, serif">Classic / Georgia</option><option value="Roboto, sans-serif">Neutral / Roboto</option></select></label></fieldset></section>
      <section className="design-live"><span className="workspace-eyebrow">PREVIEW BEFORE SAVE</span><h2>{school.name}</h2><p>{school.motto}</p><DesignPreview layout={theme.layout} theme={theme} name={school.name} logo={school.logo} large/><p className="design-help">Your records and access permissions stay with your school.</p></section></div>
      <div className="design-save-bar"><div><strong>{school.name}</strong><span>{DESIGNS.find(d=>d.id===theme.layout)?.name || 'Existing school design'}</span></div><button disabled={busy} onClick={save}>{busy?'Saving...':'Save appearance'}</button></div>
    </>}
  </main>;
}
