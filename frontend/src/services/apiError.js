export function getApiErrorMessage(error, fallback = 'Unable to load this module. Please try again.') {
  const status = error?.response?.status;
  const data = error?.response?.data;
  const detail = data?.detail || data?.error || data?.message;

  if (status === 403) {
    return "You don't have access to this module. Your account may not have permission for this feature, or your school assignment may need to be updated. Contact your school administrator if you believe this is a mistake.";
  }

  if (status === 401) {
    return 'Your session has expired. Please sign in again.';
  }

  if (status === 404) {
    return detail || 'The requested school record could not be found.';
  }

  return detail || fallback;
}

export function isAccessDenied(error) {
  return error?.response?.status === 403;
}
