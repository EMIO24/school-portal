"""Read text questions from bounded Word OOXML documents; never execute content."""
import io
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MAX_FILE = 5 * 1024 * 1024

def parse_questions(upload):
    if not upload.name.lower().endswith('.docx'):
        raise ValueError('Upload a Word .docx file.')
    if upload.size > MAX_FILE:
        raise ValueError('The Word file must be 5 MB or smaller.')
    try:
        with zipfile.ZipFile(upload) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(e.file_size for e in entries) > 20 * 1024 * 1024:
                raise ValueError('The document is too large to import.')
            info = archive.getinfo('word/document.xml')
            if info.file_size > 2 * 1024 * 1024:
                raise ValueError('The document text is too large to import.')
            xml = archive.read(info)
        # Only UTF-8 OOXML is accepted; rejecting declarations before parsing prevents entity expansion.
        decoded = xml.decode('utf-8-sig')
        if '<!DOCTYPE' in decoded.upper() or '<!ENTITY' in decoded.upper():
            raise ValueError('This document contains unsupported XML declarations.')
        root = ET.fromstring(decoded)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, UnicodeError, RuntimeError, NotImplementedError) as error:
        raise ValueError('Could not read this Word file. Save it as .docx and try again.') from error
    if any(element.tag.rsplit('}', 1)[-1] in ('drawing', 'pict', 'oMath', 'altChunk', 'object') for element in root.iter()):
        raise ValueError('This upload supports text questions only. Remove images, equations or embedded objects and enter those separately.')
    lines = []
    for paragraph in root.iter(W + 'p'):
        content = ''.join('\n' if node.tag == W + 'br' else node.text or '' for node in paragraph.iter() if node.tag in (W + 't', W + 'br'))
        lines.extend(line.strip() for line in content.splitlines() if line.strip())
    questions = []
    current = None
    for line in lines:
        start = re.match(r'^(?:Question\s*:|\d+[.)])\s*(.+)$', line, re.I)
        option = re.match(r'^([A-D])[.):]\s*(.+)$', line)
        answer = re.match(r'^(?:Answer|Correct answer)\s*:\s*(.+)$', line, re.I)
        explanation = re.match(r'^Explanation\s*:\s*(.*)$', line, re.I)
        if start:
            if current:
                questions.append(current)
            current = {'question_text': start.group(1), 'options': [], 'correct_answer': '', 'explanation': ''}
        elif current and option:
            current['options'].append({'id': option.group(1), 'text': option.group(2), 'image_url': None})
        elif current and answer:
            current['correct_answer'] = answer.group(1).strip()
        elif current and explanation:
            current['explanation'] = explanation.group(1)
        elif current and not current['options'] and not current['correct_answer']:
            current['question_text'] += '\n' + line
        else:
            raise ValueError('Use the template: start each question with "Question:" or a typed number, followed by options and "Answer:".')
    if current:
        questions.append(current)
    if not 1 <= len(questions) <= 200:
        raise ValueError('Include between 1 and 200 questions using the template format.')
    for index, question in enumerate(questions, 1):
        options = question['options']
        ids = [option['id'] for option in options]
        if options:
            question['correct_answer'] = question['correct_answer'].upper()
            if len(ids) < 2 or len(set(ids)) != len(ids) or question['correct_answer'] not in ids:
                raise ValueError(f'Question {index}: provide 2–4 unique options and an Answer matching an option letter.')
        if not question['correct_answer'] or len(question['correct_answer']) > 10:
            raise ValueError(f'Question {index}: an answer is required (maximum 10 characters for fill-in answers).')
        question['question_type'] = 'mcq' if options else 'fill_blank'
    return questions

def question_template():
    lines = ['Question: What is 2 + 2?', 'A. 3', 'B. 4', 'C. 5', 'D. 6', 'Answer: B',
             'Explanation: Adding two and two gives four.', 'Question: The capital of Nigeria is _____.', 'Answer: Abuja']
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr('word/document.xml', '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + ''.join('<w:p><w:r><w:t>' + escape(line) + '</w:t></w:r></w:p>' for line in lines) + '<w:sectPr/></w:body></w:document>')
    return out.getvalue()