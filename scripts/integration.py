"""Prepare and check the local browser-test sandbox. Run from any directory."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.integration'
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.db import transaction

PASSWORD = 'PortalTest!2026'
STATE = ROOT / '.testing'


def seed():
    from accounts.models import CustomUser, ParentStudentLink
    from tenants.models import School
    from academics.models import AcademicSession, Term
    from enrollment.models import ClassLevel, ClassArm, Subject, StudentProfile, StaffProfile, SubjectAssignment
    from timetable.models import Period, TimetableEntry
    from fees.models import FeeCategory, FeeSchedule
    accounts = []
    fixtures = {}
    with transaction.atomic():
        for index, slug in enumerate(['qa-school', 'qa-other-school'], start=1):
            school, _ = School.objects.update_or_create(slug=slug, defaults={
                'name': 'QA School' if index == 1 else 'QA Other School', 'subdomain': slug, 'is_active': True,
                'subscription_plan': 'premium',  # Fixture schools exercise all paid features.
            })
            users = {}
            for offset, role in enumerate(['school_admin', 'teacher', 'student', 'parent', 'unlinked_student'], start=1):
                actual_role = 'student' if role == 'unlinked_student' else role
                email = f'{role}@{slug}.test'
                user, _ = CustomUser.objects.get_or_create(email=email, defaults={'id': index * 1000 + offset})
                user.role = actual_role
                user.school = school
                user.first_name = 'QA'
                user.last_name = role.replace('_', ' ').title()
                user.is_active = True
                user.must_change_password = False
                user.set_password(PASSWORD)
                user.save()
                users[role] = user
                accounts.append({'email': email, 'password': PASSWORD, 'role': actual_role, 'school': slug, 'account_id': user.id})
            session, _ = AcademicSession.objects.update_or_create(school=school, name='2026/2027', defaults={
                'start_date': '2026-09-01', 'end_date': '2027-07-31', 'is_current': True,
            })
            term, _ = Term.objects.update_or_create(session=session, name='first', defaults={
                'start_date': '2026-09-01', 'end_date': '2026-12-18', 'is_current': True,
            })
            level, _ = ClassLevel.objects.get_or_create(school=school, name='JSS1', defaults={'order_index': 1})
            arm, _ = ClassArm.objects.update_or_create(school=school, class_level=level, name='A', defaults={'class_teacher': users['teacher']})
            subject, _ = Subject.objects.get_or_create(school=school, code='MATH', defaults={'name': 'Mathematics', 'category': 'core'})
            subject.class_levels.add(level)
            teacher, _ = StaffProfile.objects.get_or_create(user=users['teacher'], defaults={'school': school})
            teacher.subjects_taught.add(subject)
            teacher.assigned_classes.add(arm)
            SubjectAssignment.objects.get_or_create(school=school, teacher=teacher, subject=subject, class_arm=arm, session=session, term=term)
            students = []
            for role in ['student', 'unlinked_student']:
                student, _ = StudentProfile.objects.update_or_create(user=users[role], defaults={
                    'school': school, 'current_class': arm, 'gender': 'female', 'dob': '2012-05-10',
                    'guardian_name': 'QA Parent', 'guardian_email': users['parent'].email,
                })
                students.append(student)
            ParentStudentLink.objects.get_or_create(parent=users['parent'], student=students[0], school=school)
            period, _ = Period.objects.update_or_create(school=school, order_index=1, defaults={
                'name': 'Period 1', 'start_time': '08:00', 'end_time': '09:00', 'is_break': False,
            })
            TimetableEntry.objects.get_or_create(school=school, term=term, class_arm=arm, period=period, day_of_week='MON', defaults={
                'teacher': users['teacher'], 'subject': subject,
            })
            category, _ = FeeCategory.objects.get_or_create(school=school, name='Tuition')
            schedule, _ = FeeSchedule.objects.update_or_create(school=school, term=term, class_level=level, fee_category=category, defaults={'amount': '15000.00'})
            fixtures[slug] = {'school': school.id, 'session': session.id, 'term': term.id, 'class_arm': arm.id,
                'class_level': level.id, 'subject': subject.id, 'teacher_profile': teacher.id, 'teacher_account': users['teacher'].id,
                'student_profile': students[0].id, 'student_account': students[0].user_id,
                'unlinked_student_profile': students[1].id, 'unlinked_student_account': students[1].user_id,
                'fee_schedule': schedule.id}
    (STATE / 'accounts.json').write_text(json.dumps(accounts, indent=2), encoding='utf-8')
    (STATE / 'fixtures.json').write_text(json.dumps(fixtures, indent=2), encoding='utf-8')
    print('Prepared two schools, ten role accounts, classes, teacher assignments, timetable and fees.')
    print('Local credentials: .testing/accounts.json; fixture IDs: .testing/fixtures.json')


def check():
    from django.test import Client
    from django.core.cache import cache
    cache.clear()
    accounts = json.loads((STATE / 'accounts.json').read_text(encoding='utf-8'))
    checks = []
    for account in accounts:
        client = Client(HTTP_X_SCHOOL_SLUG=account['school'])
        response = client.post('/api/auth/login/', {'email': account['email'], 'password': account['password']}, content_type='application/json')
        assert response.status_code == 200, f"Login failed for {account['email']}: HTTP {response.status_code}"
        token = response.json()['access']
        response = client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Bearer {token}')
        assert response.status_code == 200, f"Profile failed for {account['email']}: HTTP {response.status_code}"
        assert response.json()['id'] == account['account_id']
        checks.append({'account': account['email'], 'login': 'passed', 'profile': 'passed'})
    response = Client(HTTP_X_SCHOOL_SLUG='qa-school').get('/api/school/me/')
    assert response.status_code == 200, f'School branding failed: HTTP {response.status_code}'
    import requests
    try:
        requests.get('https://example.invalid/no-outbound-test')
    except requests.ConnectionError as error:
        assert 'disabled in the integration sandbox' in str(error)
    else:
        raise AssertionError('Outbound HTTP guard is not active')
    report = {'mode': 'in-process Django HTTP client; no browser or live server', 'accounts': checks,
              'branding': 'passed', 'outbound_http_guard': 'passed'}
    (STATE / 'readiness.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Readiness passed: 10 logins, 10 authenticated profiles, school branding and outbound HTTP guard.')



def check_live():
    from urllib.request import Request, urlopen
    def request(path, body=None, token=None, school='qa-school'):
        headers = {'X-School-Slug': school}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if body is not None:
            headers['Content-Type'] = 'application/json'
        req = Request('http://127.0.0.1:8001' + path,
                      data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urlopen(req, timeout=15) as response:
            return json.load(response)
    assert request('/health/')['status'] == 'ok'
    with urlopen('http://127.0.0.1:3001', timeout=30) as response:
        assert response.status == 200 and b'<html' in response.read().lower(), 'Frontend did not serve HTML'
    accounts = json.loads((STATE / 'accounts.json').read_text(encoding='utf-8'))
    for account in accounts:
        login = request('/api/auth/login/', {'email': account['email'], 'password': account['password']}, school=account['school'])
        profile = request('/api/auth/me/', token=login['access'], school=account['school'])
        assert profile['id'] == account['account_id'], 'Live profile ID mismatch'
    report = {'backend_health': 'passed', 'frontend_html': 'passed', 'live_logins': len(accounts),
              'live_authenticated_profiles': len(accounts), 'browser_workflows': 'not started'}
    (STATE / 'live-readiness.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Live readiness passed: frontend HTML, backend health, 10 logins and 10 authenticated profiles.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'check', 'live-check', 'serve'])
    args = parser.parse_args()
    expected = (STATE / 'portal.sqlite3').resolve()
    assert Path(settings.DATABASES['default']['NAME']).resolve() == expected, 'Refusing to use a non-sandbox database'
    if args.action == 'prepare':
        call_command('migrate', interactive=False, verbosity=0)
        seed()
        check()
    elif args.action == 'check':
        check()
    elif args.action == 'live-check':
        check_live()
    else:
        if not (STATE / 'fixtures.json').exists():
            parser.error('Run prepare first.')
        call_command('runserver', '127.0.0.1:8001', use_reloader=False)

if __name__ == '__main__':
    main()
