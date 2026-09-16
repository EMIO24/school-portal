import io
import zipfile
from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from .docx_import import parse_questions, question_template

class DocxImportTests(SimpleTestCase):
    def upload(self, content, name='questions.docx'):
        return SimpleUploadedFile(name, content)
    def test_template_extracts_multiple_questions_and_answers(self):
        questions = parse_questions(self.upload(question_template()))
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]['correct_answer'], 'B')
        self.assertEqual(questions[0]['options'][1]['text'], '4')
        self.assertEqual(questions[1]['question_type'], 'fill_blank')
        self.assertEqual(questions[1]['correct_answer'], 'Abuja')
    def test_rejects_non_word_and_corrupt_files(self):
        for upload in [self.upload(b'text', 'questions.csv'), self.upload(b'not a zip')]:
            with self.assertRaises(ValueError):
                parse_questions(upload)
    def document(self, xml):
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w') as archive:
            archive.writestr('word/document.xml', xml)
        return self.upload(content.getvalue())
    def test_rejects_entity_declarations(self):
        with self.assertRaisesMessage(ValueError, 'XML declarations'):
            parse_questions(self.document('<!DOCTYPE x [<!ENTITY y "expanded">]><x>&y;</x>'))
    def test_rejects_images_instead_of_silently_losing_content(self):
        with self.assertRaisesMessage(ValueError, 'text questions only'):
            parse_questions(self.document('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:drawing/></w:document>'))
    def test_rejects_missing_answer(self):
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Question: What is two plus two?</w:t></w:r></w:p></w:document>'
        with self.assertRaisesMessage(ValueError, 'answer is required'):
            parse_questions(self.document(xml))