import re
from django.test import SimpleTestCase
from .scratch_pdf import scratch_cards_pdf

class ScratchPDFTests(SimpleTestCase):
    def test_all_cards_and_pins_are_in_multipage_pdf(self):
        rows = [(f'SERIAL-{i}', f'{i:010}') for i in range(23)]
        pdf = scratch_cards_pdf('QA School', 'First Term', rows)
        self.assertTrue(pdf.startswith(b'%PDF-1.4'))
        self.assertIn(b'/Count 3', pdf)
        for serial, pin in rows:
            self.assertIn(serial.encode(), pdf)
            self.assertIn(('PIN: ' + pin).encode(), pdf)
        xref = int(re.search(rb'startxref\n(\d+)', pdf)[1])
        self.assertTrue(pdf[xref:].startswith(b'xref'))
        offsets = re.findall(rb'(\d{10}) 00000 n', pdf)
        for index, offset in enumerate(offsets, 1):
            self.assertTrue(pdf[int(offset):].startswith(f'{index} 0 obj'.encode()))
    def test_unused_export_contains_no_pins(self):
        pdf = scratch_cards_pdf('School', 'Batch', [('SERIAL', 'secret-pin')], include_pins=False)
        self.assertIn(b'SERIAL', pdf)
        self.assertNotIn(b'secret-pin', pdf)
        self.assertIn(b'Serial numbers only', pdf)
    def test_empty_batch_is_readable_pdf(self):
        self.assertIn(b'No unused cards', scratch_cards_pdf('School', 'Batch', [], False))