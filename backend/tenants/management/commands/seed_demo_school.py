import os
from datetime import date, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, ParentStudentLink
from academics.models import AcademicSession, Holiday, Term
from analytics.models import AnalyticsSnapshot
from attendance.models import AttendanceRecord, AttendanceSession
from cbt.models import CBTExam, Question, Topic
from enrollment.models import (
    ClassArm,
    ClassLevel,
    StaffProfile,
    StudentProfile,
    Subject,
    SubjectAssignment,
)
from fees.models import (
    FeeCategory, FeePayment, FeeSchedule, PaymentException, PaymentOrder,
    SchoolPaymentAccount,
)
from gradebook.models import AffectiveDomain, PsychomotorDomain, ScoreEntry
from gradebook.scoring import policy_for
from notifications.models import NotificationLog, NotificationTemplate
from results.models import ResultRemark
from timetable.models import Period, TimetableEntry
from tenants.models import School


DEMO_SLUG = "greenfield-demo"


class Command(BaseCommand):
    help = "Create a polished, isolated demo school with branding, teachers, students and parents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete and recreate only the Greenfield demo tenant.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("DEMO_SCHOOL_PASSWORD")
        if not password:
            raise CommandError(
                "DEMO_SCHOOL_PASSWORD is required. Set it in Railway Variables before running this command."
            )

        existing = School.objects.filter(slug=DEMO_SLUG).first()
        if existing and not options["reset"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Demo school already exists (id={existing.id}). "
                    "Run with --reset to rebuild it."
                )
            )
            return
        if existing:
            # Financial audit/history models deliberately use PROTECT in
            # production. A demo reset is an explicit destructive operation,
            # so remove only this demo tenant's protected finance records first.
            # PaymentException protects PaymentOrder, and PaymentOrder protects
            # School/User/Student/Invoice; delete in dependency order.
            demo_orders = PaymentOrder.objects.filter(school=existing)
            PaymentException.objects.filter(school=existing).delete()
            demo_orders.delete()
            FeePayment.objects.filter(school=existing).delete()
            existing.delete()

        school = School.objects.create(
            name="Greenfield International Academy",
            slug=DEMO_SLUG,
            subdomain=DEMO_SLUG,
            logo=os.environ.get(
                "DEMO_SCHOOL_LOGO_URL",
                "https://raw.githubusercontent.com/EMIO24/school-portal/production-readiness-check/frontend/public/greenfield-academy-logo.svg",
            ),
            theme_config={
                "layout": "scholar",
                "primary_color": "#173B56",
                "secondary_color": "#256D85",
                "accent_color": "#D8A548",
                "font_family": "Roboto, sans-serif",
            },
            address="12 Learning Avenue, Lagos, Nigeria",
            phone="+2348000000001",
            email="hello@greenfield.demo",
            motto="Knowledge, Character, Excellence",
            registration_number="DEMO-GIA-001",
            subscription_plan="premium",
            approval_status="approved",
            is_active=True,
            platform_notes="PAIDEIA DEMO TENANT — safe to recreate with seed_demo_school --reset.",
        )

        session = AcademicSession.objects.create(
            school=school,
            name="2026/2027",
            start_date=date(2026, 9, 7),
            end_date=date(2027, 7, 30),
            is_current=True,
        )
        term = Term.objects.create(
            session=session,
            name="first",
            start_date=date(2026, 9, 7),
            end_date=date(2026, 12, 18),
            next_term_begins=date(2027, 1, 11),
            is_current=True,
        )

        admin = CustomUser.objects.create_user(
            email="admin@greenfield.demo",
            password=password,
            first_name="Grace",
            last_name="Okafor",
            school=school,
            role="school_admin",
            phone_number="+2348000000010",
            must_change_password=False,
        )
        StaffProfile.objects.create(
            user=admin,
            school=school,
            gender="female",
            phone=admin.phone_number,
            qualification="msc",
            specialization="School Administration",
            date_employed=date(2022, 8, 15),
        )

        level_names = ["JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3"]
        levels = {}
        arms = []
        for index, level_name in enumerate(level_names):
            level = ClassLevel.objects.create(
                school=school,
                name=level_name,
                order_index=index,
                is_final_year=(level_name == "SS3"),
            )
            levels[level_name] = level
            for arm_name in ("A", "B"):
                arms.append(
                    ClassArm.objects.create(
                        school=school,
                        class_level=level,
                        name=arm_name,
                    )
                )

        subject_specs = [
            ("Mathematics", "MTH", "core"),
            ("English Language", "ENG", "core"),
            ("Basic Science", "BSC", "core"),
            ("Computer Studies", "ICT", "core"),
            ("Civic Education", "CIV", "core"),
            ("Social Studies", "SOS", "core"),
            ("Biology", "BIO", "core"),
            ("Chemistry", "CHM", "core"),
            ("Physics", "PHY", "core"),
            ("Economics", "ECO", "elective"),
            ("Government", "GOV", "elective"),
            ("Literature in English", "LIT", "elective"),
        ]
        subjects = []
        for name, code, category in subject_specs:
            subject = Subject.objects.create(
                school=school,
                name=name,
                code=code,
                category=category,
                max_ca_score=40,
                max_exam_score=60,
            )
            if code in {"BIO", "CHM", "PHY", "ECO", "GOV", "LIT"}:
                subject.class_levels.set([levels["SS1"], levels["SS2"], levels["SS3"]])
            else:
                subject.class_levels.set(list(levels.values()))
            subjects.append(subject)

        teacher_names = [
            ("Adebayo", "Johnson"), ("Chinwe", "Eze"), ("Fatima", "Bello"),
            ("Samuel", "Okon"), ("Ngozi", "Nwosu"), ("Ibrahim", "Musa"),
            ("Tolu", "Adeyemi"), ("Blessing", "Udo"), ("Daniel", "Ojo"),
            ("Esther", "Afolabi"), ("Michael", "Ekanem"), ("Mary", "Abubakar"),
        ]
        teachers = []
        for i, (first, last) in enumerate(teacher_names, start=1):
            user = CustomUser.objects.create_user(
                email=f"teacher{i}@greenfield.demo",
                password=password,
                first_name=first,
                last_name=last,
                school=school,
                role="teacher",
                phone_number=f"+234801000{i:04d}",
                must_change_password=False,
            )
            profile = StaffProfile.objects.create(
                user=user,
                school=school,
                gender="female" if i % 2 == 0 else "male",
                phone=user.phone_number,
                qualification="bsc" if i % 3 else "msc",
                specialization=subjects[(i - 1) % len(subjects)].name,
                date_employed=date(2023, 9, min(i, 28)),
            )
            teachers.append(profile)

        for i, arm in enumerate(arms):
            teacher = teachers[i % len(teachers)]
            arm.class_teacher = teacher.user
            arm.save(update_fields=["class_teacher"])
            teacher.assigned_classes.add(arm)

        assignment_count = 0
        for arm_index, arm in enumerate(arms):
            eligible = [s for s in subjects if arm.class_level in s.class_levels.all()]
            for subject_index, subject in enumerate(eligible):
                teacher = teachers[(arm_index + subject_index) % len(teachers)]
                SubjectAssignment.objects.create(
                    school=school,
                    teacher=teacher,
                    subject=subject,
                    class_arm=arm,
                    session=session,
                    term=term,
                )
                teacher.subjects_taught.add(subject)
                teacher.assigned_classes.add(arm)
                assignment_count += 1

        first_names = [
            "David", "Sarah", "Emmanuel", "Ada", "Joshua", "Zainab", "Daniel", "Grace",
            "Michael", "Amara", "Samuel", "Aisha", "Joseph", "Favour", "Nathan", "Esther",
            "Chinedu", "Mary", "Tobi", "Hauwa",
        ]
        last_names = [
            "Adeyemi", "Okafor", "Bello", "Eze", "Johnson", "Musa", "Okon", "Nwosu",
            "Afolabi", "Udo", "Ojo", "Abubakar",
        ]

        students = []
        for i in range(1, 121):
            first = first_names[(i - 1) % len(first_names)]
            last = last_names[((i - 1) // len(first_names) + i) % len(last_names)]
            arm = arms[(i - 1) % len(arms)]
            user = CustomUser.objects.create_user(
                email=f"student{i}@greenfield.demo",
                password=password,
                first_name=first,
                last_name=last,
                school=school,
                role="student",
                must_change_password=False,
            )
            student = StudentProfile.objects.create(
                user=user,
                school=school,
                current_class=arm,
                dob=date(2010 + (i % 6), ((i - 1) % 12) + 1, ((i - 1) % 27) + 1),
                gender="female" if i % 2 == 0 else "male",
                state_of_origin="Lagos",
                guardian_name=f"Mr/Mrs {last}",
                guardian_phone=f"+234802000{i:04d}",
                guardian_email=f"parent{((i - 1) // 2) + 1}@greenfield.demo",
                guardian_relationship="guardian",
            )
            students.append(student)

        parents = []
        for i in range(1, 61):
            children = students[(i - 1) * 2 : i * 2]
            family_name = children[0].user.last_name
            parent = CustomUser.objects.create_user(
                email=f"parent{i}@greenfield.demo",
                password=password,
                first_name="Parent",
                last_name=family_name,
                school=school,
                role="parent",
                phone_number=f"+234803000{i:04d}",
                must_change_password=False,
            )
            parents.append(parent)
            for child in children:
                ParentStudentLink.objects.create(
                    parent=parent,
                    student=child,
                    school=school,
                    relationship="guardian",
                )

        # Calendar / holidays
        holidays = [
            Holiday.objects.create(term=term, name="Independence Day", start_date=date(2026, 10, 1), end_date=date(2026, 10, 1), holiday_type="public"),
            Holiday.objects.create(term=term, name="Mid-Term Break", start_date=date(2026, 10, 29), end_date=date(2026, 10, 30), holiday_type="school"),
            Holiday.objects.create(term=term, name="First Term Examination Break", start_date=date(2026, 12, 7), end_date=date(2026, 12, 11), holiday_type="exam_break"),
        ]

        # School-day periods and a conflict-free timetable generated from the
        # authoritative SubjectAssignment rows.
        period_specs = [
            ("Assembly", time(7, 45), time(8, 0), True),
            ("Period 1", time(8, 0), time(8, 40), False),
            ("Period 2", time(8, 40), time(9, 20), False),
            ("Period 3", time(9, 20), time(10, 0), False),
            ("Short Break", time(10, 0), time(10, 20), True),
            ("Period 4", time(10, 20), time(11, 0), False),
            ("Period 5", time(11, 0), time(11, 40), False),
            ("Lunch Break", time(11, 40), time(12, 20), True),
            ("Period 6", time(12, 20), time(13, 0), False),
            ("Period 7", time(13, 0), time(13, 40), False),
        ]
        periods = [
            Period.objects.create(school=school, name=name, start_time=start, end_time=end, order_index=i, is_break=is_break)
            for i, (name, start, end, is_break) in enumerate(period_specs, start=1)
        ]
        teaching_periods = [p for p in periods if not p.is_break]
        days = ["MON", "TUE", "WED", "THU", "FRI"]
        occupied_class, occupied_teacher = set(), set()
        timetable_entries = []
        for assignment in SubjectAssignment.objects.filter(school=school, term=term).select_related("teacher__user", "class_arm", "subject"):
            placed = False
            for day in days:
                for period in teaching_periods:
                    class_key = (assignment.class_arm_id, day, period.id)
                    teacher_key = (assignment.teacher.user_id, day, period.id)
                    if class_key in occupied_class or teacher_key in occupied_teacher:
                        continue
                    entry = TimetableEntry.objects.create(
                        school=school, term=term, class_arm=assignment.class_arm,
                        subject=assignment.subject, teacher=assignment.teacher.user,
                        day_of_week=day, period=period,
                    )
                    timetable_entries.append(entry)
                    occupied_class.add(class_key)
                    occupied_teacher.add(teacher_key)
                    placed = True
                    break
                if placed:
                    break
            if not placed:
                raise CommandError(f"Could not place timetable assignment {assignment.id} without a conflict.")

        # Historical daily attendance gives dashboards meaningful percentages.
        # Ten school days are enough to demonstrate present/late/absent/excused.
        attendance_dates = [
            date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17), date(2026, 9, 18),
            date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25),
        ]
        attendance_sessions = []
        attendance_records = 0
        for day_index, attendance_date in enumerate(attendance_dates):
            for arm_index, arm in enumerate(arms):
                session_row = AttendanceSession.objects.create(
                    school=school, class_arm=arm, teacher=arm.class_teacher,
                    term=term, date=attendance_date, mode="daily", is_finalized=True,
                )
                attendance_sessions.append(session_row)
                for student in [s for s in students if s.current_class_id == arm.id]:
                    selector = (student.id + day_index + arm_index) % 20
                    status = "absent" if selector == 0 else "late" if selector == 1 else "excused" if selector == 2 else "present"
                    AttendanceRecord.objects.create(
                        attendance_session=session_row, student=student.user,
                        status=status, remark="Demo attendance record" if status != "present" else "",
                    )
                    attendance_records += 1

        # Use the school's real term scoring policy. Seed published scores for
        # every student/eligible subject so results, broadsheets and analytics
        # are testable from all role portals.
        scoring = policy_for(school, term, create=True)
        score_entries = []
        result_remarks = []
        for student_index, student in enumerate(students):
            eligible_subjects = [s for s in subjects if student.current_class.class_level in s.class_levels.all()]
            totals = []
            for subject_index, subject in enumerate(eligible_subjects):
                base = 55 + ((student_index * 7 + subject_index * 5) % 36)
                component_scores = {
                    "first_test": str(min(10, 5 + base % 6)),
                    "second_test": str(min(10, 5 + (base + 2) % 6)),
                    "assignment": str(min(10, 6 + (base + 1) % 5)),
                    "project": str(min(5, 3 + base % 3)),
                    "practical": str(min(5, 3 + (base + 1) % 3)),
                    "exam_score": str(min(60, 30 + base % 31)),
                }
                teacher_assignment = SubjectAssignment.objects.get(term=term, class_arm=student.current_class, subject=subject)
                entry = ScoreEntry.objects.create(
                    school=school, student=student.user, subject=subject,
                    class_arm=student.current_class, session=session, term=term,
                    teacher=teacher_assignment.teacher.user, policy=scoring,
                    component_scores=component_scores, review_state="approved", is_published=True,
                )
                score_entries.append(entry)
                totals.append(entry.total_score)
            average = sum(totals, Decimal("0")) / len(totals)
            result_remarks.append(ResultRemark.objects.create(
                school=school, student=student.user, term=term, class_arm=student.current_class,
                class_teacher_remark="A positive term. Keep working consistently.",
                principal_remark="Good progress. Aim even higher next term.",
                total_score=sum(totals, Decimal("0")), average_score=average,
                subjects_offered=len(totals),
            ))
            AffectiveDomain.objects.create(
                school=school, student=student.user, class_arm=student.current_class, term=term,
                punctuality=4, neatness=4, honesty=5, attentiveness=4,
                relationship_with_others=4, leadership=3, creativity=4,
                sport_games=3, handling_of_tools=4,
            )
            PsychomotorDomain.objects.create(
                school=school, student=student.user, class_arm=student.current_class, term=term,
                handwriting=4, drawing=3, verbal_fluency=4, musical_skills=3,
            )
        for arm in arms:
            rows = sorted([r for r in result_remarks if r.class_arm_id == arm.id], key=lambda r: r.average_score, reverse=True)
            for position, remark in enumerate(rows, start=1):
                ResultRemark.objects.filter(pk=remark.pk).update(computed_position=position)

        # Premium CBT demo: reusable question bank plus a live test exam for
        # JSS1A. Its window is relative to seeding so it remains testable.
        math = next(s for s in subjects if s.code == "MTH")
        jss1a = next(a for a in arms if a.class_level.name == "JSS1" and a.name == "A")
        topic = Topic.objects.create(school=school, subject=math, class_level=levels["JSS1"], name="Whole Numbers")
        questions = []
        for i in range(1, 21):
            a, b = i + 3, (i % 5) + 2
            answer = a + b
            options = [
                {"id": "A", "text": str(answer), "image_url": None},
                {"id": "B", "text": str(answer + 1), "image_url": None},
                {"id": "C", "text": str(answer - 1), "image_url": None},
                {"id": "D", "text": str(answer + 2), "image_url": None},
            ]
            questions.append(Question.objects.create(
                school=school, subject=math, topic=topic, class_level=levels["JSS1"],
                question_text=f"What is {a} + {b}?", question_type="mcq",
                difficulty=["easy", "medium", "hard"][i % 3],
                cognitive_level="application" if i % 3 else "knowledge",
                options=options, correct_answer="A",
                explanation=f"{a} + {b} = {answer}.", created_by=teachers[0].user,
            ))
        now = timezone.now()
        cbt_exam = CBTExam.objects.create(
            school=school, title="JSS1 Mathematics Demo CBT", subject=math,
            term=term, session=session, created_by=teachers[0].user,
            start_datetime=now - timedelta(days=1), end_datetime=now + timedelta(days=30),
            duration_minutes=20, instructions="Answer all 10 questions. You may review answers before submission.",
            selection_mode="random_from_bank",
            random_config=[{"topic_id": topic.id, "count": 10}],
            randomize_questions=True, randomize_options=True, allow_review=True,
            show_score_immediately=True, status="published",
        )
        cbt_exam.class_arms.add(jss1a)

        # Communication templates and representative logs.
        fee_template = NotificationTemplate.objects.create(
            school=school, name="Outstanding Fee Reminder", type="both",
            subject="Greenfield fee reminder",
            body="Dear parent, please review your child's outstanding first-term fees in the portal.",
            category="fee",
        )
        result_template = NotificationTemplate.objects.create(
            school=school, name="Result Published", type="email",
            subject="First Term result is available",
            body="Your child's First Term result is now available in the Greenfield parent portal.",
            category="result",
        )
        for i, student in enumerate(students[:12]):
            NotificationLog.objects.create(
                school=school, template=fee_template if i % 2 else result_template,
                channel="email", recipient_email=student.guardian_email, student=student,
                message_body=(fee_template.body if i % 2 else result_template.body),
                status="sent", sent_at=timezone.now() - timedelta(days=i % 5),
            )

        # Pre-populate a dashboard snapshot; production can still recompute it.
        AnalyticsSnapshot.objects.create(
            school=school, term=term,
            data={
                "demo": True,
                "active_students": len(students),
                "teachers": len(teachers),
                "classes": len(arms),
                "attendance_sessions": len(attendance_sessions),
                "published_score_entries": len(score_entries),
                "cbt_questions": len(questions),
                "note": "Seeded snapshot for Greenfield sales/demo testing.",
            },
        )

        # Realistic first-term fee obligations. These are the same FeeSchedule
        # records consumed by the existing parent/student Paystack checkout.
        fee_specs = [
            ("Tuition Fee", "First-term tuition and academic services", 75000),
            ("Development Levy", "School development and facilities levy", 10000),
            ("ICT Levy", "Digital learning and ICT services", 5000),
        ]
        fee_categories = []
        for name, description, _ in fee_specs:
            fee_categories.append(
                FeeCategory.objects.create(
                    school=school,
                    name=name,
                    description=description,
                    is_compulsory=True,
                )
            )

        fee_schedules = []
        due_date = date(2026, 10, 2)
        for level in levels.values():
            for category, (_, _, amount) in zip(fee_categories, fee_specs):
                fee_schedules.append(
                    FeeSchedule.objects.create(
                        school=school,
                        term=term,
                        class_level=level,
                        fee_category=category,
                        amount=amount,
                        due_date=due_date,
                    )
                )

        # Seed a few historical/manual payments so finance screens demonstrate
        # paid, part-paid and unpaid families. Most students remain outstanding
        # and can be used for the real Paystack test checkout.
        tuition_by_level = {
            schedule.class_level_id: schedule
            for schedule in fee_schedules
            if schedule.fee_category.name == "Tuition Fee"
        }
        for student in students[:8]:
            schedule = tuition_by_level[student.current_class.class_level_id]
            amount = 75000 if student.pk % 2 == 0 else 30000
            FeePayment.objects.create(
                school=school,
                student=student,
                fee_schedule=schedule,
                amount_paid=amount,
                payment_date=date(2026, 9, 15),
                method="bank_transfer",
                recorded_by=admin,
            )

        # A genuine Paystack subaccount is required by the production checkout.
        # Never commit or invent one. Supplying this Railway variable connects
        # the demo school to the existing Paystack flow.
        demo_subaccount = os.environ.get("DEMO_PAYSTACK_SUBACCOUNT_CODE", "").strip()
        paystack_connected = False
        if demo_subaccount:
            SchoolPaymentAccount.objects.create(
                school=school,
                mode=settings.PAYSTACK_MODE,
                subaccount_code=demo_subaccount,
                business_name=school.name,
                bank_name="Demo settlement account",
                account_last_four="0000",
            )
            paystack_connected = True

        self.stdout.write(self.style.SUCCESS("Greenfield International Academy demo created."))
        self.stdout.write(f"School ID: {school.id} | slug: {school.slug} | plan: {school.subscription_plan}")
        self.stdout.write("Brand: #173B56 / #256D85 / #D8A548 with demo logo")
        self.stdout.write(f"Students: {len(students)} | Teachers: {len(teachers)} | Parents: {len(parents)}")
        self.stdout.write(f"Classes: {len(arms)} | Subjects: {len(subjects)} | Assignments: {assignment_count}")
        self.stdout.write(f"Calendar: {len(holidays)} holidays | Timetable: {len(periods)} periods / {len(timetable_entries)} lessons")
        self.stdout.write(f"Attendance: {len(attendance_sessions)} sessions / {attendance_records} records")
        self.stdout.write(f"Results: {len(score_entries)} published scores / {len(result_remarks)} student remarks")
        self.stdout.write(f"CBT: {len(questions)} reusable questions | Exam: {cbt_exam.title}")
        self.stdout.write(f"Notifications: 2 templates / 12 sent demo logs | Analytics snapshot: ready")
        self.stdout.write(f"Fee categories: {len(fee_categories)} | Fee schedules: {len(fee_schedules)}")
        self.stdout.write("Per student: Tuition ₦75,000 + Development ₦10,000 + ICT ₦5,000 = ₦90,000")
        if paystack_connected:
            self.stdout.write(self.style.SUCCESS(f"Paystack {settings.PAYSTACK_MODE} settlement account connected."))
        else:
            self.stdout.write(self.style.WARNING(
                "Fees are ready, but Paystack checkout is not connected. "
                "Set DEMO_PAYSTACK_SUBACCOUNT_CODE to a real Paystack test subaccount and rerun with --reset."
            ))
        self.stdout.write("Admin: admin@greenfield.demo")
        self.stdout.write("Teacher example: teacher1@greenfield.demo")
        self.stdout.write("Parent example: parent1@greenfield.demo")
        self.stdout.write("Student example: student1@greenfield.demo")
        self.stdout.write("Passwords come from DEMO_SCHOOL_PASSWORD and are never stored in source control.")
