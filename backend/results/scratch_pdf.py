"""Printable scratch-card sheets without native PDF dependencies."""
import io

def scratch_cards_pdf(school_name, batch_name, rows, include_pins=True):
    branding = school_name if isinstance(school_name, dict) else {'school_name': school_name}
    school_name = branding.get('school_name') or 'School'
    contact_line = branding.get('school_contact_line') or ''
    motto = branding.get('school_motto') or ''
    registration = branding.get('school_registration_number') or ''
    rows = list(rows)
    chunks = [rows[i:i + 10] for i in range(0, len(rows), 10)] or [[]]
    objects = [b'', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    page_ids = []

    def literal(value):
        return str(value).encode('cp1252', 'replace').replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)').replace(b'\r', b' ').replace(b'\n', b' ')

    for page_number, cards in enumerate(chunks, 1):
        commands = []
        def text(x, y, value, size=11):
            commands.append(b'BT /F1 ' + str(size).encode() + b' Tf ' + f'{x} {y} Td ('.encode() + literal(value) + b') Tj ET')
        text(36, 807, str(school_name)[:70], 16)
        if motto:
            text(36, 789, str(motto)[:90], 9)
        if contact_line:
            text(36, 775, str(contact_line)[:115], 8)
        if registration:
            text(36, 762, ('Reg. No: ' + str(registration))[:90], 8)
        text(36, 746, ('Scratch cards: ' if include_pins else 'Unused serials: ') + str(batch_name)[:65], 11)
        text(36, 730, 'Keep the original PDF: PINs cannot be recovered.' if include_pins else 'Serial numbers only. Use the original download for PINs.', 9)
        for index, row in enumerate(cards):
            x = 36 + (index % 2) * 266
            y = 580 - (index // 2) * 125
            commands.append(f'{x} {y} 254 112 re S'.encode())
            text(x + 12, y + 100, 'RESULT CHECKING CARD' if include_pins else 'UNUSED SERIAL', 11)
            text(x + 12, y + 74, 'Serial:', 10)
            text(x + 12, y + 57, row[0], 10)
            text(x + 12, y + 31, 'PIN: ' + str(row[1]) if include_pins else 'Status: unused', 12)
        if not cards:
            text(36, 720, 'No unused cards in this batch.')
        text(36, 32, f'Page {page_number} of {len(chunks)}', 9)
        stream = b'\n'.join(commands)
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>'.encode())
        objects.append(b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream')
    objects[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    objects[1] = ('<< /Type /Pages /Kids [' + ' '.join(f'{i} 0 R' for i in page_ids) + f'] /Count {len(page_ids)} >>').encode()
    out = io.BytesIO()
    out.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = out.tell()
    out.write(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        out.write(f'{offset:010} 00000 n \n'.encode())
    out.write(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return out.getvalue()