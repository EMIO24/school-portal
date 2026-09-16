import api from './api';

// Browser navigation cannot attach the in-memory bearer token. Fetch protected
// downloads through the shared client before handing the blob to the browser.
export async function downloadFile(url, filename) {
  try {
    const { data } = await api.get(url, { responseType: 'blob' });
    const objectUrl = URL.createObjectURL(data);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    try { link.click(); }
    finally { link.remove(); URL.revokeObjectURL(objectUrl); }
    return true;
  } catch {
    window.alert('Could not download the file. Please try again.');
    return false;
  }
}
