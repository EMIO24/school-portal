// One component tree; presets select structural treatments and semantic tokens.
export const DESIGNS = [
  {id:'classic',name:'Paideia Classic',tag:'Formal and structured',description:'A traditional sidebar, divided content and restrained academic cards.',colors:['#173B56','#256D85','#D8A548'],font:'Georgia, serif',structure:'sidebar'},
  {id:'modern-academy',name:'Modern Academy',tag:'Open and spacious',description:'An airy masthead, wide navigation and generous dashboard spacing.',colors:['#195D72','#337F91','#E3B860'],font:"'Segoe UI', sans-serif",structure:'masthead'},
  {id:'executive',name:'Executive',tag:'Leadership focused',description:'A right-side navigation panel and compact management overview.',colors:['#243E42','#397A7C','#DFAD67'],font:"'Segoe UI', sans-serif",structure:'right'},
  {id:'minimal',name:'Minimal',tag:'Content first',description:'A quiet navigation rail, flat surfaces and reduced visual noise.',colors:['#394956','#69808E','#BBC6CB'],font:'Arial, sans-serif',structure:'rail'},
  {id:'scholar',name:'Scholar',tag:'Academic clarity',description:'A deep-colour sidebar and clear result-oriented hierarchy.',colors:['#173B56','#256D85','#D8A548'],font:"'Segoe UI', sans-serif",structure:'sidebar'},
  {id:'horizon',name:'Horizon',tag:'Warm and welcoming',description:'A soft masthead, friendly rounded cards and room to breathe.',colors:['#176C67','#329A90','#E4B666'],font:"'Segoe UI', sans-serif",structure:'masthead'},
  {id:'prestige',name:'Prestige',tag:'Elegant and composed',description:'A framed school identity, classic type and refined section rhythm.',colors:['#55334C','#79566B','#C3A05A'],font:'Georgia, serif',structure:'framed'},
  {id:'compact-pro',name:'Compact Pro',tag:'Operational density',description:'A narrow rail, tighter cards and efficient table spacing.',colors:['#263F55','#49677C','#C8A65C'],font:'Arial, sans-serif',structure:'rail'},
  {id:'campus',name:'Campus',tag:'Broad operational view',description:'A full-width school masthead and prominent dashboard sections.',colors:['#145B4B','#248C72','#E3B860'],font:"'Segoe UI', sans-serif",structure:'masthead'},
  {id:'nova',name:'Nova',tag:'Contemporary energy',description:'A split navigation rail, bold headings and distinctive action cards.',colors:['#343B80','#5864A2','#E5A868'],font:'Roboto, sans-serif',structure:'rail'},
];
export const LEGACY_DESIGNS = {studio:'rail',heritage:'framed'};
export const designStructure = id => DESIGNS.find(design => design.id === id)?.structure || LEGACY_DESIGNS[id] || 'sidebar';
export const baseLayout = id => ({masthead:'campus',rail:'studio',right:'executive',framed:'heritage'}[designStructure(id)] || 'scholar');
export const knownDesign = id => DESIGNS.some(design => design.id === id) || Object.hasOwn(LEGACY_DESIGNS,id);
export const DEFAULT_DESIGN = DESIGNS[0];
