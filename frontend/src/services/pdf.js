// Build a multi-page PDF report in the browser. Canvas preserves the displayed
// Unicode text without requiring downloadable PDF fonts.
export function reportPdf(title, lines) {
  const canvas = document.createElement('canvas');
  canvas.width = 1240; canvas.height = 1754;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('PDF rendering is unavailable in this browser.');
  ctx.font = '24px sans-serif';
  const wrapped = [];
  for (const line of lines) {
    for (const paragraph of String(line ?? '').split('\n')) {
      let current = '';
      for (const character of paragraph) {
        if (ctx.measureText(current + character).width > 1110) { wrapped.push(current); current = ''; }
        current += character;
      }
      wrapped.push(current);
    }
  }
  const pages = [];
  for (let offset = 0; offset < Math.max(wrapped.length, 1); offset += 43) {
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 1240, 1754);
    ctx.fillStyle = '#15243a'; ctx.font = 'bold 30px sans-serif';
    ctx.fillText(title, 65, 85, 1110);
    ctx.font = '24px sans-serif';
    wrapped.slice(offset, offset + 43).forEach((line, index) => ctx.fillText(line, 65, 145 + index * 34));
    ctx.font = '20px sans-serif';
    ctx.fillText('Page ' + (pages.length + 1) + ' of ' + Math.max(1, Math.ceil(wrapped.length / 43)), 65, 1700);
    pages.push(Uint8Array.from(atob(canvas.toDataURL('image/jpeg', 0.95).split(',')[1]), c => c.charCodeAt(0)));
  }
  const encoder = new TextEncoder();
  const encode = text => encoder.encode(text);
  const objects = [null, null];
  const pageIds = [];
  for (const jpg of pages) {
    const pageId = objects.length + 1, imageId = pageId + 1, streamId = pageId + 2;
    pageIds.push(pageId);
    objects.push([encode('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Img ' + imageId + ' 0 R >> >> /Contents ' + streamId + ' 0 R >>')]);
    objects.push([encode('<< /Type /XObject /Subtype /Image /Width 1240 /Height 1754 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ' + jpg.length + ' >>\nstream\n'), jpg, encode('\nendstream')]);
    const stream = 'q 595 0 0 842 0 0 cm /Img Do Q';
    objects.push([encode('<< /Length ' + stream.length + ' >>\nstream\n' + stream + '\nendstream')]);
  }
  objects[0] = [encode('<< /Type /Catalog /Pages 2 0 R >>')];
  objects[1] = [encode('<< /Type /Pages /Count ' + pages.length + ' /Kids [' + pageIds.map(id => id + ' 0 R').join(' ') + '] >>')];
  const chunks = [encode('%PDF-1.4\n')], offsets = [0];
  let size = chunks[0].length;
  function append(chunk) { chunks.push(chunk); size += chunk.length; }
  objects.forEach((object, index) => {
    offsets.push(size); append(encode((index + 1) + ' 0 obj\n'));
    object.forEach(append); append(encode('\nendobj\n'));
  });
  const xref = size;
  append(encode('xref\n0 ' + offsets.length + '\n0000000000 65535 f \n' +
    offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('') +
    'trailer\n<< /Size ' + offsets.length + ' /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF'));
  return new Blob(chunks, { type: 'application/pdf' });
}

export function downloadReport(title, lines, filename) {
  try {
    const url = URL.createObjectURL(reportPdf(title, lines));
    const link = document.createElement('a');
    link.href = url; link.download = filename;
    document.body.appendChild(link);
    link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch {
    window.alert('Could not create the PDF. Please try again in your browser.');
  }
}