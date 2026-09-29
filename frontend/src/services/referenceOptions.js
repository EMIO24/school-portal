import api from './api';

// Small reference collections only. Student/staff directories remain paginated.
export async function referenceOptions(path) {
  const rows = [];
  let page = 1;
  while (true) {
    const {data} = await api.get(path + (page === 1 ? '' : `${path.includes('?') ? '&' : '?'}page=${page}`));
    rows.push(...(Array.isArray(data) ? data : data.results));
    if (Array.isArray(data) || !data.next) return {data:rows};
    page += 1;
  }
}
