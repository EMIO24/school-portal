"""Bounded CSV migration of a school's current operational records."""
import csv
import io
import json
import re
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ParentStudentLink
from accounts.parent_auth import phone_value
from accounts.permissions import IsSchoolAdmin
from academics.models import Term
from tenants.models import PlatformEvent, School
from .models import (ClassArm, ClassLevel, MigrationStudentReference, StaffProfile,
                     StudentProfile, Subject, SubjectAssignment)

User = get_user_model()
DOMAINS = {
    'classes': (('class_level', 'class_arm'), ('class_level', 'class_arm')),
    'subjects': (('code', 'name'), ('code', 'name', 'class_level', 'class_levels')),
    'students': (('student_ref', 'first_name', 'last_name', 'class_level'),
                 ('student_ref', 'first_name', 'last_name', 'class_level', 'class_arm', 'email', 'dob', 'gender',
                  'state_of_origin', 'guardian_name', 'guardian_phone', 'guardian_email', 'guardian_relationship')),
    'staff': (('first_name', 'last_name', 'email'),
              ('first_name', 'last_name', 'email', 'phone', 'dob', 'gender', 'qualification',
               'specialization', 'date_employed', 'state_of_origin')),
    'parents': (('first_name', 'last_name', 'email', 'phone'),
                ('first_name', 'last_name', 'email', 'phone')),
    'parent_links': (('parent_email', 'student_ref', 'relationship'),
                     ('parent_email', 'student_ref', 'relationship')),
    'assignments': (('teacher_email', 'class_level', 'class_arm', 'subject_code'),
                    ('teacher_email', 'class_level', 'class_arm', 'subject_code')),
}
ALIASES = {'regno': 'student_ref', 'studentnumber': 'student_ref',
           'teacheremail': 'teacher_email', 'parentemail': 'parent_email',
           'subjectcode': 'subject_code', 'classarm': 'class_arm',
           'classlevel': 'class_level'}
PROTECTED = {'id', 'pk', 'school', 'schoolid', 'tenant', 'tenantid', 'userid',
             'studentid', 'staffid', 'password', 'passwordhash', 'issuperuser',
             'isstaff', 'permissions', 'groups', 'role', 'plan', 'entitlements',
             'audit', 'actor', 'admissionnumber', 'subscriptionplan',
             'platformowner', 'isactive', 'mustchangepassword', 'schoolname'}
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def email(value, field='email'):
    value = value.strip().lower()
    if len(value) > 254:
        raise ValueError(field, 'Email address is too long.')
    try:
        validate_email(value)
    except DjangoValidationError:
        raise ValueError(field, 'Enter a valid email address.')
    return value


def date(value, field='dob'):
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(field, 'Use YYYY-MM-DD or DD/MM/YYYY.')


def unique(items, field, predicate, missing):
    matches = [item for item in items if predicate(item)]
    if len(matches) != 1:
        raise ValueError(field, missing if not matches else 'Reference is ambiguous; use one exact existing record.')
    return matches[0]


def level_for(school, value, *, allow_new=False):
    name = value.strip().upper().replace(' ', '')
    if name not in dict(ClassLevel.LEVEL_CHOICES):
        raise ValueError('class_level', 'Use an existing supported level such as JSS1 or SS2.')
    level = ClassLevel.objects.filter(school=school, name=name).first()
    if not level and not allow_new:
        raise ValueError('class_level', f'Create class level {name} in Classes first.')
    return name, level


def arm_for(school, level, value):
    arms = list(ClassArm.objects.filter(school=school, class_level=level))
    return unique(arms, 'class_arm',
                  lambda arm: arm.name.casefold() == value.strip().casefold() or
                  arm.full_name.casefold() == value.strip().casefold() or
                  (not value.strip() and len(arms) == 1),
                  'Choose one existing class arm in this school.')


def identify(domain, row):
    if domain == 'students': return row['student_ref'].casefold()
    if domain in ('staff', 'parents'): return row['email'].casefold()
    if domain == 'parent_links': return (row['parent_email'].casefold(), row['student_ref'].casefold())
    if domain == 'classes': return (row['class_level'].casefold(), row['class_arm'].casefold())
    if domain == 'subjects': return row['code'].casefold()
    return (row['teacher_email'].casefold(), row['class_level'].casefold(),
            row['class_arm'].casefold(), row['subject_code'].casefold())


def assess(domain, row, school):
    """Return (action, resolved data); perform no writes."""
    if domain == 'classes':
        name, level = level_for(school, row['class_level'], allow_new=True)
        arm_name = row['class_arm'].strip()
        if len(arm_name) > 10: raise ValueError('class_arm', 'Use at most 10 characters.')
        existing = ClassArm.objects.filter(school=school, class_level=level) if level else []
        arm = next((a for a in existing if a.name.casefold() == arm_name.casefold()), None)
        return ('REUSE' if arm else 'CREATE', {'level_name': name, 'arm_name': arm_name})
    if domain == 'subjects':
        code, name = row['code'].upper(), row['name']
        if len(code) > 10 or len(name) > 100: raise ValueError('code', 'Check subject code (10) and name (100) lengths.')
        if row.get('class_level') and row.get('class_levels'):
            raise ValueError('class_levels', 'Use class_level or class_levels, not both.')
        names = row.get('class_levels', '').split(';') if row.get('class_levels') else [row.get('class_level')] if row.get('class_level') else []
        levels = [level_for(school, item)[1] for item in names]
        if len(levels) != len({item.pk for item in levels}):
            raise ValueError('class_levels', 'List each class level once.')
        subject = Subject.objects.filter(school=school, code__iexact=code).first()
        if subject and subject.name.casefold() != name.casefold():
            raise ValueError('code', 'This subject code already has a different name; review it manually.')
        if subject and levels and set(subject.class_levels.values_list('pk', flat=True)) != {item.pk for item in levels}:
            raise ValueError('class_level', 'Existing subject has different class coverage; review it manually.')
        return ('REUSE' if subject else 'CREATE', {'code': code, 'name': name, 'levels': levels})
    if domain == 'students':
        ref = row['student_ref']
        if len(ref) > 80: raise ValueError('student_ref', 'Use at most 80 characters.')
        _, level = level_for(school, row['class_level'])
        arm = arm_for(school, level, row.get('class_arm', ''))
        dob = date(row.get('dob', ''))
        gender = row.get('gender', '').casefold()
        if gender not in ('', 'male', 'female', 'm', 'f'):
            raise ValueError('gender', 'Use male or female.')
        student_email = email(row['email']) if row.get('email') else None
        if row.get('guardian_email'): email(row['guardian_email'], 'guardian_email')
        for field, limit in (('state_of_origin', 50), ('guardian_name', 150), ('guardian_phone', 20)):
            if len(row.get(field, '')) > limit: raise ValueError(field, f'Use at most {limit} characters.')
        relationship = row.get('guardian_relationship', '').casefold()
        if relationship and relationship not in dict(StudentProfile.RELATIONSHIP_CHOICES):
            raise ValueError('guardian_relationship', 'Choose a supported guardian relationship.')
        identity = MigrationStudentReference.objects.filter(school=school, reference__iexact=ref).select_related('student__user').first()
        if identity:
            student = identity.student
            if (student.school_id != school.pk or student.user.school_id != school.pk or
                student.user.first_name.casefold() != row['first_name'].casefold() or
                student.user.last_name.casefold() != row['last_name'].casefold() or
                student.current_class_id != arm.pk or student.dob != dob or
                (student_email and student.user.email != student_email)):
                raise ValueError('student_ref', 'Reference is already linked to different student details; review manually.')
            return 'REUSE', {}
        if student_email and User.objects.filter(email__iexact=student_email).exists():
            raise ValueError('email', 'This email cannot be used; review the existing account.')
        if StudentProfile.objects.filter(school=school, user__first_name__iexact=row['first_name'],
                user__last_name__iexact=row['last_name'], dob=dob, current_class=arm).exists():
            raise ValueError('student_ref', 'A matching student already exists; review before linking a source reference.')
        return 'CREATE', {'arm': arm, 'dob': dob, 'gender': {'m': 'male', 'f': 'female'}.get(gender, gender), 'email': student_email}
    if domain == 'staff':
        if len(row.get('phone', '')) > 20: raise ValueError('phone', 'Use at most 20 characters.')
        if len(row.get('specialization', '')) > 150 or len(row.get('state_of_origin', '')) > 50:
            raise ValueError('specialization', 'Check specialization and state of origin lengths.')
        gender = row.get('gender', '').casefold()
        qualification = row.get('qualification', '').casefold()
        if gender and gender not in dict(StaffProfile.GENDER_CHOICES):
            raise ValueError('gender', 'Use male or female.')
        if qualification and qualification not in dict(StaffProfile.QUALIFICATION_CHOICES):
            raise ValueError('qualification', 'Choose a supported qualification code.')
        dob = date(row.get('dob', ''))
        employed = date(row.get('date_employed', ''), 'date_employed')
        staff_email = email(row['email'])
        user = User.objects.filter(email__iexact=staff_email).first()
        if user:
            if (user.school_id != school.pk or user.role != 'teacher' or
                user.first_name.casefold() != row['first_name'].casefold() or
                user.last_name.casefold() != row['last_name'].casefold() or
                not StaffProfile.objects.filter(school=school, user=user).exists()):
                raise ValueError('email', 'This email belongs to a different account; review manually.')
            return 'REUSE', {}
        return 'CREATE', {'email': staff_email, 'dob': dob, 'employed': employed,
                          'gender': gender, 'qualification': qualification}
    if domain == 'parents':
        parent_email = email(row['email'])
        phone = phone_value(row['phone'])
        if not phone: raise ValueError('phone', 'Enter a parent login phone number with 10 to 15 digits.')
        user = User.objects.filter(email__iexact=parent_email).first()
        if user:
            if (user.school_id != school.pk or user.role != 'parent' or
                user.phone_number != phone or not user.is_active or
                user.first_name.casefold() != row['first_name'].casefold() or
                user.last_name.casefold() != row['last_name'].casefold()):
                raise ValueError('email', 'This parent email has different account details; review manually.')
            return 'REUSE', {}
        if User.objects.filter(school=school, role='parent', phone_number=phone).exists():
            raise ValueError('phone', 'This phone belongs to another parent account; use its registered email.')
        return 'CREATE', {'email': parent_email, 'phone': phone}
    if domain == 'parent_links':
        parent = User.objects.filter(school=school, role='parent', email__iexact=email(row['parent_email'], 'parent_email'), is_active=True).first()
        if not parent: raise ValueError('parent_email', 'Import this parent in this school first.')
        identity = MigrationStudentReference.objects.filter(school=school, reference__iexact=row['student_ref']).select_related('student__user').first()
        student = identity.student if identity else StudentProfile.objects.filter(school=school, admission_number__iexact=row['student_ref']).select_related('user').first()
        if not student or student.school_id != school.pk or student.user.school_id != school.pk:
            raise ValueError('student_ref', 'Import this student reference in this school first.')
        if row['relationship'].casefold() not in dict(ParentStudentLink.RELATIONSHIP_CHOICES):
            raise ValueError('relationship', 'Choose father, mother or guardian.')
        link = ParentStudentLink.objects.filter(school=school, parent=parent, student=student).first()
        if link and link.relationship != row['relationship'].casefold():
            raise ValueError('relationship', 'This link exists with another relationship; review manually.')
        return ('REUSE' if link else 'CREATE', {'parent': parent, 'student': student})
    teacher_email = email(row['teacher_email'], 'teacher_email')
    teacher = StaffProfile.objects.filter(school=school, user__school=school, user__role='teacher',
                                          user__email__iexact=teacher_email).first()
    if not teacher: raise ValueError('teacher_email', 'Import this teacher in this school first.')
    _, level = level_for(school, row['class_level'])
    arm = arm_for(school, level, row['class_arm'])
    subject = Subject.objects.filter(school=school, code__iexact=row['subject_code']).first()
    if not subject: raise ValueError('subject_code', 'Import this subject in this school first.')
    if subject.class_levels.exists() and not subject.class_levels.filter(pk=level.pk).exists():
        raise ValueError('subject_code', 'This subject is not offered at the selected class level.')
    term = Term.objects.filter(session__school=school, is_current=True).select_related('session').first()
    if not term: raise ValueError('term', 'Set the current academic session and term before importing assignments.')
    existing = SubjectAssignment.objects.filter(school=school, subject=subject, class_arm=arm, term=term).first()
    if existing and existing.teacher_id != teacher.pk:
        raise ValueError('teacher_email', 'This subject/class/term already belongs to another teacher; review manually.')
    return ('REUSE' if existing else 'CREATE', {'teacher': teacher, 'arm': arm, 'subject': subject, 'term': term})


def create(domain, row, school, data):
    if domain == 'classes':
        level, _ = ClassLevel.objects.get_or_create(school=school, name=data['level_name'])
        ClassArm.objects.create(school=school, class_level=level, name=data['arm_name'])
    elif domain == 'subjects':
        subject = Subject.objects.create(school=school, code=data['code'], name=data['name'])
        if data['levels']: subject.class_levels.add(*data['levels'])
    elif domain == 'students':
        user = User.objects.create_user(email=data['email'], password=None,
            first_name=row['first_name'], last_name=row['last_name'], role='student',
            school=school, must_change_password=True)
        student = StudentProfile.objects.create(user=user, school=school, current_class=data['arm'],
            dob=data['dob'], gender=data['gender'], state_of_origin=row.get('state_of_origin', ''),
            guardian_name=row.get('guardian_name', ''), guardian_phone=row.get('guardian_phone', ''),
            guardian_email=row.get('guardian_email', '').lower(),
            guardian_relationship=row.get('guardian_relationship', '').lower())
        user.set_password(student.admission_number)
        user.save(update_fields=['password'])
        MigrationStudentReference.objects.create(school=school, reference=row['student_ref'], student=student)
    elif domain == 'staff':
        user = User.objects.create_user(email=data['email'], password=None,
            first_name=row['first_name'], last_name=row['last_name'], role='teacher',
            school=school, must_change_password=True)
        staff = StaffProfile.objects.create(user=user, school=school, phone=row.get('phone', ''),
            dob=data['dob'], date_employed=data['employed'], gender=data['gender'],
            qualification=data['qualification'], specialization=row.get('specialization', ''),
            state_of_origin=row.get('state_of_origin', ''))
        user.set_password(staff.staff_id)
        user.save(update_fields=['password'])
    elif domain == 'parents':
        User.objects.create_user(email=data['email'], password=None, first_name=row['first_name'],
            last_name=row['last_name'], role='parent', school=school, phone_number=data['phone'],
            must_change_password=False)
    elif domain == 'parent_links':
        ParentStudentLink.objects.create(school=school, parent=data['parent'],
            student=data['student'], relationship=row['relationship'].casefold())
    else:
        SubjectAssignment.objects.create(school=school, teacher=data['teacher'],
            subject=data['subject'], class_arm=data['arm'], term=data['term'], session=data['term'].session)


def parse_upload(request, domain):
    if domain not in DOMAINS: raise ValidationError({'error': 'Unsupported migration type.'})
    upload = request.FILES.get('file')
    if not upload or not upload.name.lower().endswith('.csv') or upload.size > MAX_BYTES:
        raise ValidationError({'error': 'Upload a UTF-8 CSV file of at most 2 MB.'})
    try:
        content = upload.read(MAX_BYTES + 1).decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValidationError({'error': 'Save the file as UTF-8 CSV.'})
    if len(content.encode('utf-8')) > MAX_BYTES or '\x00' in content:
        raise ValidationError({'error': 'CSV is too large or contains invalid characters.'})
    try:
        reader = csv.DictReader(io.StringIO(content, newline=''), strict=True)
        headers = reader.fieldnames or []
    except csv.Error:
        raise ValidationError({'error': 'CSV structure is malformed.'})
    if not headers or any(not h.strip() for h in headers) or len(headers) != len(set(headers)) or len(headers) != len(set(map(normalized, headers))):
        raise ValidationError({'error': 'CSV headers must be present and unique.'})
    if any(normalized(h) in PROTECTED or any(word in normalized(h) for word in ('password', 'secret', 'token')) for h in headers):
        raise ValidationError({'error': 'Remove system-controlled columns such as IDs, roles, passwords or school.'})
    try:
        supplied = json.loads(request.data.get('mapping', '{}'))
    except (TypeError, ValueError):
        raise ValidationError({'error': 'Column mapping must be valid JSON.'})
    if not isinstance(supplied, dict) or any(not isinstance(source, str) or source not in headers for source in supplied):
        raise ValidationError({'error': 'Column mapping refers to a missing source column.'})
    allowed = set(DOMAINS[domain][1])
    chosen = [dest for dest in supplied.values() if dest not in ('', None)]
    if any(not isinstance(dest, str) or dest not in allowed for dest in chosen) or len(set(chosen)) != len(chosen):
        raise ValidationError({'error': 'Mapping has an unsupported or duplicate destination.'})
    mapping = {source: dest for source, dest in supplied.items() if dest not in ('', None)}
    for header in headers:
        if header in supplied: continue
        normalized_header = normalized(header)
        candidate = next((field for field in allowed if normalized(field) == normalized_header), None)
        candidate = candidate or ALIASES.get(normalized_header)
        if candidate in allowed and candidate not in mapping.values(): mapping[header] = candidate
    if set(DOMAINS[domain][0]) - set(mapping.values()):
        raise ValidationError({'error': 'Map required columns: ' + ', '.join(sorted(set(DOMAINS[domain][0]) - set(mapping.values())))})
    try:
        raw_rows = list(reader)
    except csv.Error:
        raise ValidationError({'error': 'CSV structure is malformed.'})
    if len(raw_rows) > MAX_ROWS: raise ValidationError({'error': 'Import at most 2,000 rows per file.'})
    rows = []
    for number, raw in enumerate(raw_rows, 2):
        if None in raw or any(value is None for value in raw.values()):
            rows.append((number, None, ('file', 'Column count does not match the header.')))
            continue
        row = {dest: raw[source].strip() for source, dest in mapping.items()}
        if any(value.lstrip().startswith(('=', '@')) for value in row.values()):
            rows.append((number, None, ('file', 'Formula-like content is not accepted in migration fields.')))
        else:
            rows.append((number, row, None))
    return rows, [h for h in headers if h not in mapping], mapping


class MigrationCentre(APIView):
    permission_classes = [IsSchoolAdmin]
    parser_classes = [MultiPartParser]

    def get(self, request, domain=None):
        if domain:
            if domain not in DOMAINS: raise ValidationError({'error': 'Unsupported migration type.'})
            from django.http import HttpResponse
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(DOMAINS[domain][1])
            response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="paideia_{domain}_template.csv"'
            return response
        return Response({'domains': [
            {'key': key, 'required': required, 'columns': columns}
            for key, (required, columns) in DOMAINS.items()]})

    def post(self, request, domain, operation):
        if operation not in ('validate', 'import'):
            raise ValidationError({'error': 'Choose validate or import.'})
        rows, ignored, mapping = parse_upload(request, domain)
        school = request.tenant
        results, seen, seen_emails, seen_people = [], set(), set(), set()
        seen_phones, seen_assignment_slots = set(), set()
        counts = {'CREATE': 0, 'REUSE': 0, 'REJECT': 0}

        def process():
            for number, row, parse_error in rows:
                if parse_error:
                    outcome = {'row': number, 'action': 'REJECT', 'field': parse_error[0], 'reason': parse_error[1]}
                else:
                    try:
                        missing = [field for field in DOMAINS[domain][0] if not row.get(field)]
                        if missing: raise ValueError(missing[0], 'Required value is empty.')
                        for field in ('first_name', 'last_name'):
                            if len(row.get(field, '')) > 150:
                                raise ValueError(field, 'Use at most 150 characters.')
                        key = identify(domain, row)
                        if key in seen: raise ValueError('file', 'Duplicate reference in this file.')
                        seen.add(key)
                        action, data = assess(domain, row, school)
                        if domain == 'parents' and action == 'CREATE':
                            if data['phone'] in seen_phones:
                                raise ValueError('phone', 'Duplicate parent phone in this file.')
                            seen_phones.add(data['phone'])
                        if domain == 'assignments' and action == 'CREATE':
                            slot = (data['arm'].pk, data['subject'].pk, data['term'].pk)
                            if slot in seen_assignment_slots:
                                raise ValueError('subject_code', 'Another teacher in this file already has this class and subject.')
                            seen_assignment_slots.add(slot)
                        if domain == 'students' and action == 'CREATE':
                            student_email = data['email']
                            person = (row['first_name'].casefold(), row['last_name'].casefold(),
                                      data['dob'], data['arm'].pk)
                            if student_email and student_email in seen_emails:
                                raise ValueError('email', 'Duplicate email in this file.')
                            if person in seen_people:
                                raise ValueError('student_ref', 'Duplicate student details in this file.')
                            if student_email: seen_emails.add(student_email)
                            seen_people.add(person)
                        if operation == 'import' and action == 'CREATE':
                            with transaction.atomic(): create(domain, row, school, data)
                        outcome = {'row': number, 'action': action}
                    except ValueError as exc:
                        outcome = {'row': number, 'action': 'REJECT', 'field': exc.args[0], 'reason': exc.args[1]}
                    except Exception:
                        if operation == 'validate': raise
                        outcome = {'row': number, 'action': 'REJECT', 'field': 'file',
                                   'reason': 'This row could not be saved. Check its values and retry it separately.'}
                counts[outcome['action']] += 1
                results.append(outcome)

        if operation == 'import':
            with transaction.atomic():
                School.objects.select_for_update().get(pk=school.pk)
                process()
                if counts['CREATE'] or counts['REJECT']:
                    PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email,
                        action='school.migration_completed', target=str(school.pk),
                        details={'school_id': school.pk, 'domain': domain, 'counts': counts})
        else:
            process()
        return Response({'domain': domain, 'mode': operation, 'total_rows': len(rows),
                         'counts': counts, 'rows': results,
                         'warnings': [f'Ignored column: {header}' for header in ignored],
                         'mapping': mapping})
