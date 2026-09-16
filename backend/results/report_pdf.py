"""Small multipage text reports for server downloads."""
import textwrap

def text_report_pdf(title, lines):
    wrapped = [part for line in lines for part in (textwrap.wrap(str(line), 85) or [''])]
    pages = [wrapped[i:i+40] for i in range(0,len(wrapped),40)] or [[]]
    objects = [b'', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    ids = []
    def escaped(text):
        return str(text).encode('cp1252','replace').replace(b'\\',b'\\\\').replace(b'(',b'\\(').replace(b')',b'\\)').replace(b'\n',b' ').replace(b'\r',b' ')
    for page, lines in enumerate(pages,1):
        commands = [b'BT /F1 14 Tf 40 795 Td ('+escaped(title)+b') Tj ET']
        for index,line in enumerate(lines):
            commands.append(f'BT /F1 11 Tf 40 {755-index*17} Td ('.encode()+escaped(line)+b') Tj ET')
        commands.append(f'BT /F1 9 Tf 40 30 Td (Page {page} of {len(pages)}) Tj ET'.encode())
        stream=b'\n'.join(commands)
        page_id=len(objects)+1; ids.append(page_id)
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id+1} 0 R >>'.encode())
        objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
    objects[0]=b'<< /Type /Catalog /Pages 2 0 R >>'
    objects[1]=('<< /Type /Pages /Kids ['+' '.join(f'{i} 0 R' for i in ids)+f'] /Count {len(ids)} >>').encode()
    pdf=bytearray(b'%PDF-1.4\n'); offsets=[0]
    for index,obj in enumerate(objects,1):
        offsets.append(len(pdf)); pdf.extend(f'{index} 0 obj\n'.encode()+obj+b'\nendobj\n')
    xref=len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]: pdf.extend(f'{offset:010} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode())
    return bytes(pdf)