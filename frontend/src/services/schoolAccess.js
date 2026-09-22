export function schoolLoginPath(slug) {
  return `/login?school=${encodeURIComponent(slug)}`;
}

export function openSchoolLogin(slug) {
  window.location.assign(schoolLoginPath(slug));
}
