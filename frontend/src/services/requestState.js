// Read failures are safe to retry. Mutations keep their domain-specific
// reconciliation because a missing response does not prove the write failed.
export function classifyRequestFailure(error, { mutation = false } = {}) {
  const status = error?.response?.status;
  if (status === 400 || status === 422) return { kind: 'validation', message: 'Review the details and try again.' };
  if (status === 401 || status === 403) return { kind: 'authorization', message: 'You do not have access to this information. Sign in again or contact your school administrator.' };
  if (!status && error?.code === 'ECONNABORTED') return mutation
    ? { kind: 'unknown', message: "We couldn't confirm whether this was saved. Check the current record before trying again." }
    : { kind: 'timeout', message: 'This is taking longer than expected. Check your connection and retry.' };
  if (!status) return mutation
    ? { kind: 'unknown', message: "We couldn't confirm whether this was saved. Check the current record before trying again." }
    : { kind: 'network', message: "We couldn't reach Paideia. Check your connection and try again." };
  return { kind: 'server', message: "Paideia couldn't complete this request. Please try again." };
}
