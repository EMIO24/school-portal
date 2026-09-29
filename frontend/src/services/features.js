export function featureForRoute(path) {
  if (/\/(students|staff)\/import(?:\/|$)/.test(path)) return 'bulk_import';
  if (/\/(question-bank|exam-papers|online-assignments)(?:\/|$)/.test(path)) return 'cbt';
  if (/\/(term-questions|exam-manager|exam-results|exams|exam)(?:\/|$)/.test(path)) return 'term_cbt';
  if (/\/(results|scores|domains)(?:\/|$)/.test(path)) return 'results';
  if (/\/(fees|fee-setup|fee-collection)(?:\/|$)/.test(path)) return 'fees';
  if (/\/attendance(?:\/|$)/.test(path)) return 'attendance';
  if (/\/(timetable|teaching|curriculum|scheme)(?:\/|$)/.test(path)) return 'timetable';
  if (/\/(notifications|notification-templates|communications|notices)(?:\/|$)/.test(path)) return 'notifications';
  if (/\/performance(?:\/|$)/.test(path)) return 'analytics';
  if (/\/promotion(?:\/|$)/.test(path)) return 'promotion';
  if (/\/scratch-cards(?:\/|$)/.test(path)) return 'scratch_cards';
  return null;
}
export function hasFeature(school, feature) {
  return !feature || !school?.entitlements || school.entitlements.features.includes(feature);
}
