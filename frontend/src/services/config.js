// All API consumers share the same backend origin and tenant selection.
export const API_BASE_URL = (process.env.REACT_APP_API_URL || process.env.REACT_APP_API_BASE_URL || '').replace(/\/+$/, '');
// School login links select the tenant for this browser tab. The backend still
// verifies membership; this identifier never grants access by itself.
const requestedSchool = new URLSearchParams(window.location.search).get('school');
if (requestedSchool && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(requestedSchool)) {
  if ((sessionStorage.getItem('school_slug') || process.env.REACT_APP_SCHOOL_SLUG || '') !== requestedSchool) {
    localStorage.removeItem('school_theme');
    if (window.location.pathname !== '/school-preview') localStorage.removeItem('refresh_token');
  }
  sessionStorage.setItem('school_slug', requestedSchool);
}
const selectedSchool = sessionStorage.getItem('school_slug') || process.env.REACT_APP_SCHOOL_SLUG || '';
export const TENANT_HEADERS = selectedSchool ? { 'X-School-Slug': selectedSchool } : {};
