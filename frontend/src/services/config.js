// All API consumers share the same backend origin and tenant selection.
export const API_BASE_URL = (process.env.REACT_APP_API_URL || process.env.REACT_APP_API_BASE_URL || '').replace(/\/+$/, '');

// Platform owner login must stay tenant-free; school-scoped requests only apply
// to school login and tenant-specific pages. This prevents a stale school slug
// from being sent on superadmin auth requests.
const requestedSchool = new URLSearchParams(window.location.search).get('school');
if (requestedSchool && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(requestedSchool)) {
  if ((sessionStorage.getItem('school_slug') || process.env.REACT_APP_SCHOOL_SLUG || '') !== requestedSchool) {
    localStorage.removeItem('school_theme');
    if (window.location.pathname !== '/school-preview') localStorage.removeItem('refresh_token');
  }
  sessionStorage.setItem('school_slug', requestedSchool);
}

const isPlatformLogin = window.location.pathname.startsWith('/platform/');
const selectedSchool = isPlatformLogin ? '' : (sessionStorage.getItem('school_slug') || process.env.REACT_APP_SCHOOL_SLUG || '');
export const TENANT_HEADERS = selectedSchool ? { 'X-School-Slug': selectedSchool } : {};
