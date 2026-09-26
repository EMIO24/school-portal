"""Create deterministic local data for commercial-scale Basic validation."""
import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, ParentStudentLink
from academics.models import AcademicSession, Term
from attendance.models import AttendanceRecord, AttendanceSession
from enrollment.models import ClassArm, ClassLevel, StaffProfile, StudentProfile, Subject, SubjectAssignment
from fees.invoices import issue_invoice
from fees.models import FeeCategory, FeePayment, FeeSchedule, SubscriptionOffer
from gradebook.models import ScoreEntry
from gradebook.scoring import calculate, policy_for
from results.models import ResultRemark
from tenants.models import School


SLUG = 'paideia-simulation'
BOUNDARY_SLUG = 'paideia-boundary'
PASSWORD = 'Paideia-Simulation-2026!'


class Command(BaseCommand):
    help = 'Create a deterministic 500-active-student local commercial simulation.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm-development', action='store_true',
            help='Required acknowledgement that this engineering dataset is for a local/test database.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
        if module.endswith('.production') or not options['confirm_development']:
            raise CommandError('Simulation seeding is blocked unless --confirm-development is supplied outside production settings.')
        if School.objects.filter(slug__in=[SLUG, BOUNDARY_SLUG]).exists():
            raise CommandError('Simulation schools already exist. Use a clean local/test database; existing schools were not changed.')

        offer = SubscriptionOffer.objects.filter(plan='basic', amount=Decimal('800.00'), enabled=True).first()
        if not offer:
            raise CommandError('The enabled Basic offer at NGN 800 is required. Run platform bootstrap/migrations first.')

        school = School.objects.create(
            name='Paideia Commercial Simulation Academy', slug=SLUG, subdomain=SLUG,
            subscription_plan='basic', address='12 Learning Avenue, Abuja',
            phone='08000001000', email='office@simulation.test', motto='Knowledge and Character',
        )
        password = make_password(PASSWORD)
        staff_users = CustomUser.objects.bulk_create([
            CustomUser(
                school=school, role='teacher' if i < 25 else 'school_admin',
                email=f'staff{i + 1:02d}@simulation.test', first_name='Teacher' if i < 25 else 'Administrator',
                last_name=f'{i + 1:02d}', password=password, must_change_password=False,
            ) for i in range(40)
        ])
        staff = StaffProfile.objects.bulk_create([
            StaffProfile(
                school=school, user=user, staff_id=f'SIM-STAFF-{i + 1:04d}',
                gender='female' if i % 2 else 'male', qualification='bsc',
                specialization='School Operations' if i >= 25 else 'Classroom Teaching',
            ) for i, user in enumerate(staff_users)
        ])
        teachers = staff[:25]
        admin = staff_users[25]

        levels = ClassLevel.objects.bulk_create([
            ClassLevel(school=school, name=name, order_index=i, is_final_year=name == 'SS3')
            for i, name in enumerate(('JSS1', 'JSS2', 'JSS3', 'SS1', 'SS2', 'SS3'))
        ])
        arms = ClassArm.objects.bulk_create([
            ClassArm(school=school, class_level=level, name=arm)
            for level in levels for arm in ('A', 'B', 'C')
        ])
        for i, arm in enumerate(arms):
            arm.class_teacher = teachers[i].user
        ClassArm.objects.bulk_update(arms, ['class_teacher'])

        subject_names = (
            ('ENG', 'English Language'), ('MTH', 'Mathematics'), ('BSC', 'Basic Science'),
            ('SST', 'Social Studies'), ('CST', 'Computer Studies'), ('AGR', 'Agricultural Science'),
            ('PHY', 'Physics'), ('CHE', 'Chemistry'), ('BIO', 'Biology'), ('ECO', 'Economics'),
            ('GOV', 'Government'), ('LIT', 'Literature in English'), ('CRS', 'Civic and Religious Studies'),
            ('BST', 'Business Studies'), ('PHE', 'Physical and Health Education'),
        )
        subjects = Subject.objects.bulk_create([
            Subject(school=school, code=code, name=name, category='core' if i < 6 else 'elective')
            for i, (code, name) in enumerate(subject_names)
        ])
        through = Subject.class_levels.through
        through.objects.bulk_create([
            through(subject_id=subject.pk, classlevel_id=level.pk)
            for subject in subjects for level in levels
        ])

        historical_session = AcademicSession.objects.create(
            school=school, name='2025/2026', start_date=date(2025, 9, 1), end_date=date(2026, 7, 31),
        )
        historical_term = Term.objects.create(
            session=historical_session, name='third', start_date=date(2026, 4, 20), end_date=date(2026, 7, 24),
        )
        session = AcademicSession.objects.create(
            school=school, name='2026/2027', start_date=date(2026, 9, 1), end_date=date(2027, 7, 30), is_current=True,
        )
        term = Term.objects.create(
            session=session, name='first', start_date=date(2026, 9, 1), end_date=date(2026, 12, 18),
            is_current=True, next_term_begins=date(2027, 1, 11),
        )
        assignments = SubjectAssignment.objects.bulk_create([
            SubjectAssignment(
                school=school, teacher=teachers[(arm_index * 5 + subject_index) % len(teachers)],
                subject=subjects[subject_index], class_arm=arm, session=session, term=term,
            )
            for arm_index, arm in enumerate(arms) for subject_index in range(5)
        ])
        SubjectAssignment.objects.create(
            school=school, teacher=teachers[0], subject=subjects[0], class_arm=arms[0],
            session=historical_session, term=historical_term,
        )

        first_names = ('Ada', 'Chinedu', 'Amina', 'Tunde', 'Ngozi', 'Ibrahim', 'Kemi', 'Emeka', 'Zainab', 'Femi')
        last_names = ('Okafor', 'Bello', 'Adeyemi', 'Eze', 'Musa', 'Balogun', 'Nwosu', 'Garba', 'Olawale', 'Danladi')
        student_users = CustomUser.objects.bulk_create([
            CustomUser(
                school=school, role='student', email=f'student{i + 1:03d}@simulation.test' if i % 5 == 0 else None,
                first_name=first_names[i % len(first_names)], last_name=f'{last_names[(i // 10) % len(last_names)]} {i + 1:03d}',
                password=password, must_change_password=False, is_active=i < 500,
            ) for i in range(505)
        ])
        students = StudentProfile.objects.bulk_create([
            StudentProfile(
                school=school, user=user, admission_number=f'SIM-2026-{i + 1:04d}',
                status='active' if i < 500 else 'withdrawn', current_class=arms[i % len(arms)],
                gender='female' if i % 2 else 'male', dob=date(2010 + i % 5, 1 + i % 12, 1 + i % 27) if i % 4 else None,
                guardian_name=f'Guardian {i % 380 + 1:03d}', guardian_phone=f'0801{i % 380:07d}',
                guardian_relationship='guardian',
            ) for i, user in enumerate(student_users)
        ])

        parents = CustomUser.objects.bulk_create([
            CustomUser(
                school=school, role='parent', email=f'parent{i + 1:03d}@simulation.test',
                first_name='Guardian', last_name=f'{i + 1:03d}', phone_number=f'0802{i:07d}',
                password=password, must_change_password=False,
            ) for i in range(380)
        ])
        links = [
            ParentStudentLink(school=school, parent=parents[i % len(parents)], student=student, relationship='guardian')
            for i, student in enumerate(students)
        ]
        links.extend([
            ParentStudentLink(school=school, parent=parents[200 + i], student=students[i], relationship='mother')
            for i in range(20)
        ])
        ParentStudentLink.objects.bulk_create(links)

        attendance_sessions = AttendanceSession.objects.bulk_create([
            AttendanceSession(
                school=school, class_arm=arm, teacher=arm.class_teacher, term=term,
                date=date(2026, 9, 7) + timedelta(days=day), mode='daily', is_finalized=True,
            ) for arm in arms for day in range(5)
        ])
        active_by_arm = {arm.pk: [] for arm in arms}
        for student in students[:500]:
            active_by_arm[student.current_class_id].append(student.user_id)
        records = []
        for attendance_session in attendance_sessions:
            for index, user_id in enumerate(active_by_arm[attendance_session.class_arm_id]):
                marker = (index + attendance_session.date.day) % 12
                status = 'absent' if marker == 0 else 'late' if marker == 1 else 'present'
                records.append(AttendanceRecord(attendance_session=attendance_session, student_id=user_id, status=status))
        AttendanceRecord.objects.bulk_create(records)

        categories = FeeCategory.objects.bulk_create([
            FeeCategory(school=school, name=name) for name in ('Tuition', 'Development Levy', 'Activities')
        ])
        schedules = FeeSchedule.objects.bulk_create([
            FeeSchedule(
                school=school, term=term, class_level=level, fee_category=category,
                amount=Decimal('60000.00') if category.name == 'Tuition' else Decimal('10000.00'),
                due_date=date(2026, 10, 2),
            ) for level in levels for category in categories
        ])
        tuition = {row.class_level_id: row for row in schedules if row.fee_category_id == categories[0].pk}
        payments = FeePayment.objects.bulk_create([
            FeePayment(
                school=school, student=student, fee_schedule=tuition[student.current_class.class_level_id],
                amount_paid=Decimal('60000.00') if i < 100 else Decimal('30000.00'),
                payment_date=date(2026, 9, 15), method='bank_transfer', recorded_by=admin,
                receipt_number=f'SIM-REC-{i + 1:06d}',
            ) for i, student in enumerate(students[:300])
        ])

        policy = policy_for(school, term, create=True)
        historical_policy = policy_for(school, historical_term, create=True)
        score_rows = []
        states = (('draft', False), ('submitted', False), ('approved', False), ('approved', True))
        for context_index, (state, published) in enumerate(states):
            arm, subject = arms[context_index], subjects[context_index]
            assignment = next(row for row in assignments if row.class_arm_id == arm.pk and row.subject_id == subject.pk)
            for i, student in enumerate([s for s in students[:500] if s.current_class_id == arm.pk]):
                values = {'first_test': str(6 + i % 5), 'second_test': '8', 'assignment': '7', 'project': '4', 'practical': '4', 'exam_score': str(35 + i % 20)}
                total, grade, remark = calculate(policy, values)
                score_rows.append(ScoreEntry(
                    school=school, student_id=student.user_id, subject=subject, class_arm=arm,
                    session=session, term=term, teacher=assignment.teacher.user, policy=policy,
                    component_scores=values, ca_total=total - Decimal(values['exam_score']), exam_score=values['exam_score'],
                    total_score=total, grade=grade, remark=remark, review_state=state, is_published=published,
                ))
        historical_students = [s for s in students[:500] if s.current_class_id == arms[0].pk]
        historical_values = {'first_test': '8', 'second_test': '8', 'assignment': '8', 'project': '4', 'practical': '4', 'exam_score': '48'}
        historical_total, historical_grade, historical_remark = calculate(historical_policy, historical_values)
        for student in historical_students:
            score_rows.append(ScoreEntry(
                school=school, student_id=student.user_id, subject=subjects[0], class_arm=arms[0],
                session=historical_session, term=historical_term, teacher=teachers[0].user, policy=historical_policy,
                component_scores=historical_values, ca_total=historical_total - Decimal('48'), exam_score=Decimal('48'),
                total_score=historical_total, grade=historical_grade, remark=historical_remark,
                review_state='approved', is_published=True,
            ))
        scores = ScoreEntry.objects.bulk_create(score_rows)
        current_published = [row for row in scores if row.term_id == term.pk and row.is_published]
        ResultRemark.objects.bulk_create([
            ResultRemark(
                school=school, student_id=row.student_id, term=term, class_arm=row.class_arm,
                computed_position=i + 1, total_score=row.total_score, average_score=row.total_score,
                subjects_offered=1, class_teacher_remark='Steady progress.', principal_remark='Keep learning.',
            ) for i, row in enumerate(current_published)
        ])

        invoice, _ = issue_invoice(
            school_id=school.pk, term_id=term.pk, due_date=timezone.localdate() + timedelta(days=14), actor=admin,
        )
        boundary = self._boundary_school(password)

        counts = {
            'schools': 2, 'students': len(students), 'active_students': 500, 'staff': len(staff),
            'teachers': len(teachers), 'parents': len(parents), 'classes': len(arms),
            'subjects': len(subjects), 'assignments': len(assignments) + 1,
            'attendance_sessions': len(attendance_sessions), 'attendance_records': len(records),
            'fee_schedules': len(schedules), 'fee_payments': len(payments), 'score_entries': len(scores),
            'parent_links': len(links), 'invoice_amount': str(invoice.final_amount),
        }
        self.stdout.write(self.style.SUCCESS('Commercial simulation created: ' + ', '.join(f'{key}={value}' for key, value in counts.items())))
        self.stdout.write(f'Primary school id={school.pk}; boundary school id={boundary.pk}; local password={PASSWORD}')

    def _boundary_school(self, password):
        school = School.objects.create(
            name='Paideia Boundary Academy', slug=BOUNDARY_SLUG, subdomain=BOUNDARY_SLUG, subscription_plan='basic',
        )
        admin = CustomUser.objects.create(
            school=school, role='school_admin', email='admin@boundary.test', first_name='Boundary', last_name='Admin',
            password=password, must_change_password=False,
        )
        teacher = CustomUser.objects.create(
            school=school, role='teacher', email='teacher@boundary.test', first_name='Boundary', last_name='Teacher',
            password=password, must_change_password=False,
        )
        staff = StaffProfile.objects.create(school=school, user=teacher, staff_id='BOUNDARY-STAFF-0001')
        level = ClassLevel.objects.create(school=school, name='JSS1')
        arm = ClassArm.objects.create(school=school, class_level=level, name='A', class_teacher=teacher)
        subject = Subject.objects.create(school=school, code='MTH', name='Mathematics')
        subject.class_levels.add(level)
        session = AcademicSession.objects.create(
            school=school, name='2026/2027', start_date=date(2026, 9, 1), end_date=date(2027, 7, 30), is_current=True,
        )
        term = Term.objects.create(
            session=session, name='first', start_date=date(2026, 9, 1), end_date=date(2026, 12, 18), is_current=True,
        )
        user = CustomUser.objects.create(
            school=school, role='student', first_name='Boundary', last_name='Student', password=password, must_change_password=False,
        )
        student = StudentProfile.objects.create(
            school=school, user=user, admission_number='BOUNDARY-2026-0001', current_class=arm,
        )
        assignment = SubjectAssignment.objects.create(
            school=school, teacher=staff, subject=subject, class_arm=arm, session=session, term=term,
        )
        attendance_session = AttendanceSession.objects.create(
            school=school, class_arm=arm, teacher=teacher, term=term, date=date(2026, 9, 7), is_finalized=True,
        )
        AttendanceRecord.objects.create(attendance_session=attendance_session, student=user, status='present')
        category = FeeCategory.objects.create(school=school, name='Tuition')
        schedule = FeeSchedule.objects.create(
            school=school, term=term, class_level=level, fee_category=category, amount=Decimal('10000.00'),
        )
        FeePayment.objects.create(
            school=school, student=student, fee_schedule=schedule, amount_paid=Decimal('5000.00'),
            payment_date=date(2026, 9, 15), method='cash', recorded_by=admin, receipt_number='BOUNDARY-REC-0001',
        )
        policy = policy_for(school, term, create=True)
        values = {'first_test': '8', 'second_test': '8', 'assignment': '8', 'project': '4', 'practical': '4', 'exam_score': '45'}
        ScoreEntry.objects.create(
            school=school, student=user, subject=subject, class_arm=arm, session=session, term=term,
            teacher=teacher, policy=policy, component_scores=values, review_state='draft',
        )
        issue_invoice(
            school_id=school.pk, term_id=term.pk, due_date=timezone.localdate() + timedelta(days=14), actor=admin,
        )
        return school
