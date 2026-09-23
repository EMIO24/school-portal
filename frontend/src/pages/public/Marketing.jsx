import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import api from '../../services/api';
import { openSchoolLogin } from '../../services/schoolAccess';
import './Marketing.css';

const lightLogo = '/media/brand/paideia-full-light.jpeg';
const darkLogo = '/media/brand/paideia-full-dark.jpeg';
const productMedia = '/media/product';
const pages = {
  '/': ['A digital home for every school', 'Paideia gives schools a configured portal for administration, teaching, learning and family access.'],
  '/features': ['Explore the platform', 'See how school work connects across Paideia Portals.'],
  '/pricing': ['Pricing', 'Clear per-student pricing for your school portal.'],
  '/demo': ['Request a demo', 'Discuss a Paideia portal configured around your school.'],
  '/contact': ['Contact', 'Start a conversation about your school portal.'],
  '/privacy': ['Privacy draft', 'How Paideia handles school and student information.'],
  '/terms': ['Terms draft', 'Draft terms for using Paideia Portals.'],
  '/access': ['Find your school', "Enter your school's name to access its Paideia portal."],
};
const roles = [
  { name: 'Administrator', line: 'Keep the school moving.', description: 'Coordinate students, staff, subjects, calendars, fees and school operations.', areas: ['Student records', 'School calendar', 'Fee setup'], image: '01-admin-dashboard.webp', alt: 'Paideia administrator dashboard showing school operations' },
  { name: 'Teacher', line: 'Make teaching work easier to follow.', description: 'Record attendance, enter scores and see the timetable for assigned classes.', areas: ['Attendance', 'Score entry', 'Timetable'], image: '02-teacher-dashboard.webp', alt: 'Paideia teacher dashboard showing classroom tools' },
  { name: 'Student', line: 'See what matters today.', description: 'Reach timetable, results, attendance and fee information through a focused account.', areas: ['Timetable', 'Results', 'Fee status'], image: '03-student-dashboard.webp', alt: 'Paideia student dashboard showing learning and fee tools' },
  { name: 'Parent', line: 'Stay connected to your child.', description: 'Linked parents can follow results, attendance and fee information.', areas: ['Linked child', 'Results', 'Attendance'], image: '04-parent-dashboard.webp', alt: "Paideia parent portal showing a student's academic overview" },
];
const outcomes = [
  ['01', 'Run the school', 'Keep people, subjects, classes and the academic calendar in a coherent working space.'],
  ['02', 'Manage academics', 'Follow attendance and scores through to report cards and performance views.'],
  ['03', 'Understand fees', 'Set fees, track balances, verify online payments and retrieve receipts.'],
  ['04', 'Connect families', 'Give students and linked parents information relevant to their school lives.'],
];

function Layout({ children }) {
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    const [title, description] = pages[pathname] || pages['/'];
    document.title = `${title} | Paideia Portals`;
    document.querySelector('meta[name="description"]')?.setAttribute('content', description);
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', `${title} | Paideia Portals`);
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', description);
    document.querySelector('meta[property="og:image"]')?.setAttribute('content', `${window.location.origin}${lightLogo}`);
    document.querySelector('link[rel="canonical"]')?.setAttribute('href', `${window.location.origin}${pathname}`);
    setMenuOpen(false);
  }, [pathname]);
  useEffect(() => {
    if (!menuOpen) return undefined;
    const close = event => { if (event.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [menuOpen]);
  return <div className="marketing">
    <a className="marketing-skip" href="#marketing-main">Skip to content</a>
    <header className="marketing-header"><div className="marketing-shell marketing-header-inner">
      <Link className="marketing-brand" to="/" aria-label="Paideia Portals home"><img src={lightLogo} alt=""/><span>Paideia <small>PORTALS</small></span></Link>
      <button className="marketing-menu-button" type="button" aria-expanded={menuOpen} aria-controls="marketing-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? 'Close' : 'Menu'} <span aria-hidden="true">{menuOpen ? '×' : '☰'}</span></button>
      <nav id="marketing-navigation" className={menuOpen ? 'marketing-nav is-open' : 'marketing-nav'} aria-label="Main navigation">
        <Link to="/features">Features</Link><Link to="/pricing">Pricing</Link><Link to="/demo">Demo</Link><Link to="/contact">Contact</Link>
        <Link className="marketing-portal-link" to="/access">Access your portal</Link><Link className="marketing-nav-cta" to="/demo">Request a demo <span aria-hidden="true">↗</span></Link>
      </nav>
    </div></header>
    <main id="marketing-main">{children}</main>
    <footer className="marketing-footer"><div className="marketing-shell marketing-footer-inner"><img src={darkLogo} loading="lazy" alt="Paideia Portals — Cultivating minds. Building futures."/><p>Digital school environments configured for the communities they serve.</p><nav aria-label="Footer navigation"><Link to="/features">Features</Link><Link to="/pricing">Pricing</Link><Link to="/contact">Contact</Link><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link></nav></div></footer>
  </div>;
}

function Actions() { return <div className="marketing-actions"><Link className="marketing-button" to="/demo">Request a demo <span aria-hidden="true">↗</span></Link><Link className="marketing-text-link" to="/features">Explore the platform <span aria-hidden="true">→</span></Link></div>; }

function ProductComposition() { return <div className="product-composition"><div className="product-frame"><img src={`${productMedia}/01-admin-dashboard.webp`} width="1800" height="1125" alt="Paideia administrator dashboard showing school operations"/></div><div className="product-detail"><img src={`${productMedia}/04-parent-dashboard.webp`} width="1800" height="1125" alt="Paideia parent portal showing a student's academic overview"/></div><div className="product-side-note"><span className="marketing-overline">REAL PAIDEIA PORTALS</span><strong>Admin and family views</strong><small>Bright Future College · synthetic demo configuration</small></div></div>; }

function RoleShowcase() {
  const [selected, setSelected] = useState(0);
  const role = roles[selected];
  return <section className="marketing-section marketing-role-section"><div className="marketing-shell"><div className="marketing-section-intro"><p className="marketing-overline">THE PAIDEIA ECOSYSTEM</p><h2>One school. Four focused experiences.</h2><p>Everyone sees the part of school life they need, without making every role work inside the same dashboard.</p></div><div className="role-showcase"><div className="role-tabs" role="tablist" aria-label="Portal roles">{roles.map((item, index) => <button key={item.name} type="button" role="tab" id={`role-tab-${index}`} aria-controls="role-panel" aria-selected={selected === index} tabIndex={selected === index ? 0 : -1} onClick={() => setSelected(index)} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); const next = (selected + (event.key === 'ArrowRight' ? 1 : -1) + roles.length) % roles.length; setSelected(next); document.getElementById(`role-tab-${next}`)?.focus(); } }}>{item.name}</button>)}</div><div id="role-panel" className="role-panel" role="tabpanel" aria-labelledby={`role-tab-${selected}`}><div><p className="marketing-overline">{role.name.toUpperCase()} PORTAL</p><h3>{role.line}</h3><p>{role.description}</p><ul>{role.areas.map(area => <li key={area}>{area}</li>)}</ul></div><figure className="role-product"><img key={role.image} src={`${productMedia}/${role.image}`} width="1800" height="1125" loading="lazy" alt={role.alt}/><figcaption>Bright Future College · synthetic demo configuration</figcaption></figure></div></div></div></section>;
}

function Home() { return <Layout>
  <section className="marketing-hero"><div className="marketing-shell marketing-hero-grid"><div className="marketing-hero-copy"><p className="marketing-overline">A BETTER DIGITAL HOME FOR SCHOOL</p><h1>Your school deserves a portal that feels like yours.</h1><p>Paideia connects administration, teachers, students and parents in one digital environment configured for your school.</p><Actions/><Link className="marketing-existing" to="/access">Already using Paideia? Find your school <span aria-hidden="true">→</span></Link></div><div className="marketing-hero-art"><img src={lightLogo} alt="Paideia Portals — Cultivating minds. Building futures."/><ProductComposition/></div></div></section>
  <section className="marketing-proof"><div className="marketing-shell"><p className="marketing-overline">THE PRODUCT, NOT A PROMISE</p><p>School work moves across people, academics and payments. Paideia brings those workflows into one school environment while giving each role a clearer place to work.</p></div></section>
  <section className="marketing-section"><div className="marketing-shell"><div className="marketing-section-intro"><p className="marketing-overline">WHY PAIDEIA</p><h2>Make the everyday work of school feel connected.</h2></div><div className="outcome-grid">{outcomes.map(([number, title, text]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{text}</p></article>)}</div></div></section>
  <RoleShowcase/>
  <section className="marketing-section marketing-workflow"><div className="marketing-shell marketing-split"><div><p className="marketing-overline">ACADEMICS, IN CONTEXT</p><h2>From the school day to the report card.</h2><p>Attendance, score entry, results and timetable views sit alongside the people they support. Premium schools can add CBT exams and deeper performance tools.</p><Link className="marketing-text-link" to="/features">Explore academic workflows →</Link></div><figure className="media-frame"><img src={`${productMedia}/05-results-performance.webp`} width="1800" height="1125" loading="lazy" alt="Paideia student performance view showing academic progress"/></figure></div></section>
  <section className="marketing-section marketing-payments"><div className="marketing-shell marketing-split"><div><p className="marketing-overline">SCHOOL FINANCE</p><h2>From fee setup to receipt.</h2><p>Schools can define fees, see outstanding balances and offer a verified online payment flow with receipts. Payment records remain tied to the right school.</p><div className="payment-sequence" aria-label="Fee payment workflow"><span>Set fees</span><b>→</b><span>Pay</span><b>→</b><span>Verify</span><b>→</b><span>Receipt</span></div></div><figure className="media-frame media-frame-dark"><img src={`${productMedia}/06-fees-payments.webp`} width="1800" height="1125" loading="lazy" alt="Paideia fee account showing balances, payment history and receipt access"/></figure></div></section>
  <section className="marketing-section marketing-custom"><div className="marketing-shell"><div className="marketing-section-intro"><p className="marketing-overline">DESIGNED AROUND YOUR SCHOOL</p><h2>Powered by Paideia. Presented as your school.</h2><p>School branding, colours and configured layouts make each portal feel at home in its community. The examples below use synthetic demo schools.</p></div><div className="custom-portals">{[['09-customization-cedarfield.webp','Cedarfield Academy'],['10-customization-bright-future.webp','Bright Future College'],['11-customization-heritage.webp','Heritage Model School']].map(([image, name]) => <figure key={image}><img src={`${productMedia}/${image}`} width="1800" height="1125" loading="lazy" alt={`${name} synthetic Paideia portal configuration`}/><figcaption>{name} · demo configuration</figcaption></figure>)}</div></div></section>
  <section className="marketing-section marketing-steps"><div className="marketing-shell"><p className="marketing-overline">GETTING STARTED</p><h2>A considered start for every school.</h2><ol><li>Request a demo</li><li>Discuss your requirements</li><li>Configure your school portal</li><li>Onboard school users</li></ol></div></section>
  <section className="marketing-section marketing-closing"><div className="marketing-shell marketing-split"><div><p className="marketing-overline">CLEAR COMMERCIAL TERMS</p><h2>Start with what your school needs.</h2><p>Basic is ₦800 and Premium is ₦1,500 per active student per term. Schools with 100 or more active students receive an automatic 10% discount.</p><Link className="marketing-text-link" to="/pricing">Compare plans →</Link></div><div><p className="marketing-overline">BUILT WITH CARE</p><h3>Access that respects every role.</h3><p>School data is separated by tenant, account roles shape what people can access, and payments are verified before the portal records a successful transaction.</p></div></div></section>
  <section className="marketing-final-cta"><div className="marketing-shell"><p className="marketing-overline">LET'S BUILD YOUR SCHOOL'S DIGITAL HOME</p><h2>See Paideia in the context of your school.</h2><Link className="marketing-button marketing-button-light" to="/demo">Request a demo ↗</Link></div></section>
</Layout>; }

function Features() { return <Layout><section className="marketing-page-hero"><div className="marketing-shell"><p className="marketing-overline">THE PLATFORM</p><h1>Workflows that belong together.</h1><p>Paideia gives a school one configured place for the people, academic processes and financial tasks that make each term run.</p></div></section><RoleShowcase/><section className="marketing-section"><div className="marketing-shell feature-list">{outcomes.map(([number, title, text]) => <article key={number}><span>{number}</span><div><h2>{title}</h2><p>{text}</p></div></article>)}</div></section><section className="marketing-section marketing-premium"><div className="marketing-shell marketing-split"><div><p className="marketing-overline">PREMIUM CAPABILITIES</p><h2>More depth for schools ready to go further.</h2><p>Premium adds computer-based exams, question banks, analytics, bulk imports, promotion workflows and scratch cards to the Basic foundation.</p><div className="premium-list"><span>CBT & assessment</span><span>Performance analytics</span><span>Bulk student and staff imports</span><span>Promotion workflows</span></div></div><figure className="media-frame"><img src={`${productMedia}/08-cbt.webp`} width="1800" height="1125" loading="lazy" alt="Paideia Premium student exam workspace showing a synthetic mathematics test"/></figure></div></section><section className="marketing-final-cta"><div className="marketing-shell"><h2>See the platform around your school.</h2><Link className="marketing-button marketing-button-light" to="/demo">Request a demo ↗</Link></div></section></Layout>; }

function Pricing() { return <Layout><section className="marketing-page-hero"><div className="marketing-shell"><p className="marketing-overline">PRICING</p><h1>Clear plans for a connected school.</h1><p>Pricing is per active student, per term. Choose the capabilities your school needs.</p></div></section><section className="marketing-section"><div className="marketing-shell marketing-pricing-grid"><article><p className="marketing-overline">THE SCHOOL FOUNDATION</p><h2>Basic</h2><p className="marketing-price">₦800 <small>/ active student / term</small></p><p>School administration, attendance, results, fee management, receipts, timetables and notifications.</p><Link className="marketing-button" to="/demo">Request a demo ↗</Link></article><article className="pricing-premium"><p className="marketing-overline">MORE WAYS TO GROW</p><h2>Premium</h2><p className="marketing-price">₦1,500 <small>/ active student / term</small></p><p>Everything in Basic, plus CBT, analytics, bulk imports, promotion workflows and scratch cards.</p><Link className="marketing-button" to="/demo">Request a demo ↗</Link></article></div></section><section className="marketing-section marketing-pricing-note"><div className="marketing-shell marketing-split"><div><p className="marketing-overline">AUTOMATIC SCHOOL-SIZE DISCOUNT</p><h2>100+ active students? 10% off.</h2></div><p>The 10% discount applies automatically when a school has at least 100 active students. The current active-student count is used when the school starts its term checkout.</p></div></section></Layout>; }

function SchoolAccess() {
  const [name, setName] = useState('');
  const [status, setStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const submit = async event => {
    event.preventDefault();
    const normalized = name.trim().replace(/\s+/g, ' ');
    if (normalized.length < 3) { setStatus("Enter at least three letters from your school's name."); return; }
    setSubmitting(true); setStatus('');
    try {
      const { data } = await api.get('/api/school-lookup/', { params: { name: normalized } });
      if (data.found) { openSchoolLogin(data.slug); return; }
      setStatus(data.ambiguous ? 'More than one school matches that name. Enter the full school name.' : "We couldn't find that school. Check the name and try again.");
    } catch { setStatus('School access is temporarily unavailable. Please try again.'); }
    finally { setSubmitting(false); }
  };
  return <Layout><section className="marketing-page-hero"><div className="marketing-shell"><p className="marketing-overline">ACCESS YOUR PORTAL</p><h1>Find your school.</h1><p>Enter your school's name to access your Paideia portal.</p></div></section><section className="marketing-section"><div className="marketing-shell school-access-wrap"><form className="school-access-form" onSubmit={submit}><label htmlFor="school-name">School name</label><div><input id="school-name" value={name} onChange={event => setName(event.target.value)} placeholder="Type your school name" autoComplete="organization" autoFocus/><button className="marketing-button" type="submit" disabled={submitting}>{submitting ? 'Finding…' : 'Continue →'}</button></div>{status && <p role="alert">{status}</p>}<small>Use your school's registered name. Paideia will open its existing secure sign-in page.</small></form></div></section></Layout>;
}

function Demo() {
  const [form, setForm] = useState({ school_name: '', contact_name: '', email: '', phone: '', student_population: '', location: '', message: '', website: '' });
  const [status, setStatus] = useState(''); const [submitting, setSubmitting] = useState(false); const [sent, setSent] = useState(false);
  const update = event => setForm({ ...form, [event.target.name]: event.target.value });
  const submit = async event => { event.preventDefault(); if (form.website) return; setStatus(''); setSubmitting(true); try { await api.post('/api/demo-requests/', form); setSent(true); } catch (error) { const data = error.response?.data; setStatus(data?.detail || data?.error || 'Please review your details and try again.'); } finally { setSubmitting(false); } };
  return <Layout><section className="marketing-page-hero"><div className="marketing-shell"><p className="marketing-overline">A CONVERSATION ABOUT YOUR SCHOOL</p><h1>See what Paideia could look like for you.</h1><p>Tell us a little about your school. We’ll use it to shape a relevant product demonstration.</p></div></section><section className="marketing-section"><div className="marketing-shell marketing-demo-grid"><div className="demo-explainer"><h2>A useful first conversation.</h2><p>We’ll learn about your school, walk through relevant portal areas and discuss how your identity and workflows can be configured.</p><ol><li>Share your school’s details</li><li>Discuss the work you want to connect</li><li>See Paideia in context</li></ol><p>Already using Paideia? <Link to="/access">Find your school</Link>.</p></div>{sent ? <div className="demo-confirmation" role="status"><span aria-hidden="true">✓</span><h2>Your request is with us.</h2><p>Thank you for telling us about your school. Your request has been recorded.</p><Link to="/features">Explore the platform →</Link></div> : <form className="marketing-demo-form" onSubmit={submit}><h2>Request a demo</h2><p>Fields marked * are required.</p><div className="demo-fields">{[['school_name', 'School name', 'text'], ['contact_name', 'Your name', 'text'], ['email', 'Work email', 'email'], ['phone', 'Phone number', 'tel'], ['student_population', 'Approximate active students', 'number'], ['location', 'Location', 'text']].map(([name, label, type]) => <label key={name}>{label} *<input name={name} type={type} required min={type === 'number' ? 1 : undefined} maxLength={type === 'tel' ? 30 : 255} value={form[name]} onChange={update}/></label>)}</div><label className="marketing-honeypot" aria-hidden="true">Website<input name="website" tabIndex="-1" autoComplete="off" value={form.website} onChange={update}/></label><label>What would you like to discuss?<textarea name="message" maxLength="2000" rows="4" value={form.message} onChange={update}/></label>{status && <p className="demo-error" role="alert">{status}</p>}<button className="marketing-button" disabled={submitting} type="submit">{submitting ? 'Sending…' : 'Send request ↗'}</button></form>}</div></section></Layout>;
}

function Contact() { return <Layout><section className="marketing-page-hero"><div className="marketing-shell"><p className="marketing-overline">CONTACT PAIDEIA</p><h1>Start with your school’s story.</h1><p>Tell us what your school is working toward. We’ll use your demo request to start the right conversation.</p><Actions/></div></section><section className="marketing-section"><div className="marketing-shell marketing-split"><h2>A more relevant conversation begins with context.</h2><p>Official direct contact details will appear here when the business confirms them. Until then, the demo form is the reliable way to reach the Paideia team.</p></div></section></Layout>; }

function Legal({ kind }) {
  const privacy = kind === 'privacy';
  const sections = privacy ? [
  [
    "Purpose and school responsibilities",
    "Paideia provides customized digital school portals. Schools decide which educational records to enter, keep them accurate and authorize their users. Paideia operates the platform and enforces its implemented access controls. Formal data protection roles and any processing agreement are LEGAL REVIEW REQUIRED; this draft does not declare either party a controller or processor."
  ],
  [
    "Information used by the portal",
    "Records include student names, admission identifiers, optional student email, enrollment, guardian contacts and profile image references; parent accounts and child links; and staff accounts, contacts, employment details and teaching assignments. Academic records include attendance, scores, results, report remarks, school report ratings and assessment activity. Schools may collect sensitive optional demographic information for administrative purposes; it is not required for core portal functionality and access is restricted."
  ],
  [
    "Accounts, payments and enquiries",
    "Account and authentication information supports sign-in and security. Payment orders, amounts, references and receipts support subscriptions, school fees and reconciliation. Uploaded school branding and assessment images support portal use. Demo submissions include school and contact details, population, location and the message supplied, so Paideia can respond to an enquiry. Platform security and diagnostic records support service operations."
  ],
  [
    "Who can access records",
    "School and role controls restrict access. Parents need an explicit link to a child for protected child records; students access their own protected information. Authorized school administrators manage school data, and platform administrators have operational access under platform permissions. Public school lookup supplies only the information needed to reach the school portal. Existing result checking requires admission details and scratch-card credentials."
  ],
  [
    "Service providers and uploaded media",
    "Railway supports backend/database hosting, Vercel frontend hosting, Paystack online payments and Cloudinary configured image storage. Configured messaging services support email and SMS delivery. These services receive information needed for their functions. Image URLs are not a secure document vault: do not upload confidential documents through public image facilities. Provider arrangements, data locations and any transfer requirements are LEGAL REVIEW REQUIRED."
  ],
  [
    "Retention, suspension and requests",
    "Suspension restricts normal school access while preserving records; it does not immediately delete school data. Retention periods, deletion/anonymization and backup handling remain LEGAL REVIEW REQUIRED and BUSINESS DECISION REQUIRED. No retention period or deletion deadline is promised. The school administrator is the first contact for corrections to school records and account access. Contact and request procedures must be finalized before this draft becomes a final policy."
  ],
  [
    "Security and review status",
    "The platform uses implemented authentication, tenant and role controls. These controls are not a guarantee against every incident. Schools and users should protect credentials and report suspected misuse through their agreed support channel. Legal obligations for children's data, sensitive information, requests and incident notification require professional review. This draft makes no compliance certification or legal approval claim."
  ]
] : [
  [
    "The service and school accounts",
    "Paideia supplies a customized digital school portal to each participating school. Features depend on the selected plan and agreed configuration. Public school registration is subject to approval; submitting a demo request does not activate a school or create a service commitment. Authorized school representatives should confirm their service schedule before onboarding."
  ],
  [
    "School and user responsibilities",
    "Schools are responsible for accurate records, appropriate collection, permitted uploads, administrator appointments, role assignments and valid parent-child links. Users should protect credentials, change initial passwords and report compromised accounts. Student name login is school-scoped and may require an admission number when names are shared; other roles retain their existing authentication methods."
  ],
  [
    "Acceptable use",
    "Do not access accounts or school records without authorization, attempt cross-school access, share credentials with unauthorized people, scrape protected student data, bypass permissions, upload malware or malicious content, abuse assessment systems, commit payment fraud or attack service availability. School/student information must not be used unlawfully. Contractual enforcement, notices and remedies are BUSINESS / LEGAL DECISION REQUIRED."
  ],
  [
    "Subscription and payment",
    "Basic costs ₦800 per active student per term; Premium costs ₦1,500 per active student per term. A 10% discount applies automatically at 100 or more active students, using the checkout count. Schools arrange subscription payment; student school-fee payments are separate. Paystack payments require server verification before settlement. Pending or mismatched transactions need verification or review. Repeated settlement is protected against duplicate credit, but separate charges may need investigation."
  ],
  [
    "Billing questions and refunds",
    "The configured subscription duration must be confirmed against the agreed school billing term; no annual commitment or automatic debit is established by this draft. Refund eligibility, mistaken or duplicate payments, school-fee refunds, partial refunds, cancellations and disputes are BUSINESS / LEGAL DECISION REQUIRED. This draft promises neither automatic refunds nor a blanket no-refund rule. Contact the school administrator about school fees and the agreed Paideia channel about subscriptions."
  ],
  [
    "Availability, support and third parties",
    "The service uses hosting, payment, image-storage and messaging providers, including Railway, Vercel, Paystack and configured Cloudinary storage. Availability and recovery depend on operational and provider conditions. No uptime, recovery-time or support-response guarantee is established. Backup schedules, cloud-media recovery and support commitments must be confirmed in the school agreement."
  ],
  [
    "Suspension and termination",
    "Existing owner controls can suspend school access while preserving history. Payment settlement does not automatically reactivate a suspended school. Contractual grounds, notice, remedies, termination procedures, balances and export arrangements require BUSINESS / LEGAL DECISION REQUIRED approval. Ending access does not promise immediate deletion; eventual retention/deletion must follow an approved policy."
  ],
  [
    "Content, intellectual property and confidentiality",
    "School-provided educational records, branding and materials remain school content for operational purposes; this draft does not transfer their ownership to Paideia. Final platform licensing, content-processing permissions, third-party rights and confidentiality obligations are LEGAL REVIEW REQUIRED. Schools should supply only content they are authorized to use."
  ],
  [
    "Changes and unresolved legal provisions",
    "Changes to service, plans or terms need an agreed notification and acceptance procedure before these documents become final. Legal entity details, governing law, jurisdiction, liability limitations, indemnities, warranties, statutory rights and dispute procedures are LEGAL REVIEW REQUIRED. No jurisdiction, liability cap or financial guarantee is selected by this draft."
  ]
];
  return <Layout><section className="marketing-page-hero"><div className="marketing-shell"><p className="marketing-overline">DRAFT FOR BUSINESS AND LEGAL REVIEW</p><h1>{privacy ? 'Privacy' : 'Terms of service'}</h1><p>LEGAL REVIEW REQUIRED. This working draft is not legal advice or a final professionally reviewed policy.</p></div></section><section className="marketing-section"><div className="marketing-shell marketing-legal">{sections.map(([heading, text]) => <section key={heading}><h2>{heading}</h2><p>{text}</p></section>)}<h2>Contact</h2><p>Use your school administrator for school records and account matters. For a general Paideia enquiry, visit <Link to="/contact">Contact</Link> or use the existing <Link to="/demo">enquiry form</Link>. Official support and privacy-request channels still require confirmation. Do not submit passwords, payment credentials or detailed student records through that form.</p></div></section></Layout>;
}

export function MarketingPage({ page }) { return { home: <Home/>, features: <Features/>, pricing: <Pricing/>, demo: <Demo/>, contact: <Contact/>, access: <SchoolAccess/>, privacy: <Legal kind="privacy"/>, terms: <Legal kind="terms"/> }[page]; }
