from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tenants.models import School
from accounts.models import ParentStudentLink
from academics.models import AcademicSession, Term

from enrollment.models import (
    ClassLevel,
    ClassArm,
    Subject,
    StudentProfile,
    StaffProfile,
    SubjectAssignment,
)

from gradebook.models import ScoreEntry

from attendance.models import (
    AttendanceSession,
    AttendanceRecord,
)

from fees.models import (
    FeeCategory,
    FeeSchedule,
    FeePayment,
)

from cbt.models import (
    Topic,
    Question,
    CBTExam,
)


User = get_user_model()


class Command(BaseCommand):
    """
    Create synthetic pilot data for Paideia MVP testing.

    Usage:
        python manage.py seed_pilot_schools

    IMPORTANT:
    This command creates TEST DATA in the database connected
    to the current Django environment.
    """

    help = "Create five synthetic Paideia pilot schools for MVP testing."

    TEST_PASSWORD = "PilotTest!2026"

    SCHOOLS = [
        {
            "name": "Cedarfield Academy",
            "slug": "cedarfield",
            "plan": "basic",
            "address": "12 Pilot Avenue, Lagos",
            "phone": "08000001001",
            "email": "info@cedarfield.test",
            "motto": "Knowledge and Character",
        },
        {
            "name": "Bright Future College",
            "slug": "bright-future",
            "plan": "premium",
            "address": "24 Test Road, Lagos",
            "phone": "08000001002",
            "email": "info@bright-future.test",
            "motto": "Building Tomorrow",
        },
        {
            "name": "Heritage Model School",
            "slug": "heritage-model",
            "plan": "basic",
            "address": "8 Heritage Close, Lagos",
            "phone": "08000001003",
            "email": "info@heritage-model.test",
            "motto": "Learning for Life",
        },
        {
            "name": "Kingsway International College",
            "slug": "kingsway",
            "plan": "premium",
            "address": "15 Kingsway Drive, Lagos",
            "phone": "08000001004",
            "email": "info@kingsway.test",
            "motto": "Excellence Without Limits",
        },
        {
            "name": "Paideia Demo Academy",
            "slug": "paideia-demo",
            "plan": "premium",
            "address": "1 Paideia Way, Lagos",
            "phone": "08000001005",
            "email": "info@paideia-demo.test",
            "motto": "Cultivating Minds. Building Futures.",
        },
    ]

    def handle(self, *args, **options):
        """
        Django calls this method when we run:

            python manage.py seed_pilot_schools
        """

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "PAIDEIA PILOT DATA SEEDER"
            )
        )

        self.stdout.write(
            "This will create synthetic test data in the CURRENT database."
        )

        # --------------------------------------------------------
        # SAFETY CHECK
        # --------------------------------------------------------

        test_slugs = [
            school["slug"]
            for school in self.SCHOOLS
        ]

        existing = School.objects.filter(
            slug__in=test_slugs
        )

        if existing.exists():

            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    "STOPPED: Pilot schools already exist."
                )
            )

            for school in existing:
                self.stdout.write(
                    f" - {school.name} ({school.slug})"
                )

            self.stdout.write("")
            self.stdout.write(
                "No data was created."
            )

            return

        try:

            # ----------------------------------------------------
            # TRANSACTION
            # ----------------------------------------------------
            #
            # If creation fails halfway through, Django rolls
            # back the transaction instead of leaving half-created
            # pilot schools in the database.
            # ----------------------------------------------------

            with transaction.atomic():

                created_data = {}

                for school_number, school_data in enumerate(
                    self.SCHOOLS,
                    start=1,
                ):

                    data = self.create_school_dataset(
                        school_number,
                        school_data,
                    )

                    created_data[
                        school_data["slug"]
                    ] = data

            # Transaction completed successfully.

            self.print_summary(created_data)

        except Exception as exc:

            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    "SEEDING FAILED"
                )
            )

            self.stdout.write(
                self.style.ERROR(
                    f"{type(exc).__name__}: {exc}"
                )
            )

            self.stdout.write("")
            self.stdout.write(
                "The transaction has been rolled back."
            )

            raise CommandError(
                "Pilot school creation failed."
            ) from exc

    # ============================================================
    # USER CREATION
    # ============================================================

    def create_user(
        self,
        school,
        email,
        first_name,
        last_name,
        role,
        phone="",
    ):

        return User.objects.create_user(
            email=email,
            password=self.TEST_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            role=role,
            school=school,
            phone_number=phone,
            must_change_password=False,
        )

    # ============================================================
    # STAFF PROFILE CREATION
    # ============================================================

    def create_staff_profile(
        self,
        user,
        school,
        specialization="",
    ):

        return StaffProfile.objects.create(
            user=user,
            school=school,
            gender="male",
            phone=user.phone_number,
            qualification="bsc",
            specialization=specialization,
            date_employed=date(2025, 9, 1),
            employment_status="active",
        )

    # ============================================================
    # CREATE ONE COMPLETE SCHOOL
    # ============================================================

    def create_school_dataset(
        self,
        school_number,
        school_data,
    ):

        self.stdout.write("")
        self.stdout.write(
            "=" * 55
        )

        self.stdout.write(
            f"Creating {school_data['name']}..."
        )

        self.stdout.write(
            "=" * 55
        )

        # --------------------------------------------------------
        # SCHOOL
        # --------------------------------------------------------

        school = School.objects.create(
            name=school_data["name"],
            slug=school_data["slug"],
            subdomain=school_data["slug"],
            subscription_plan=school_data["plan"],
            approval_status="approved",
            is_active=True,
            address=school_data["address"],
            phone=school_data["phone"],
            email=school_data["email"],
            motto=school_data["motto"],
            theme_config={
                "layout": "scholar",
                "primary_color": "#173B56",
                "secondary_color": "#256D85",
                "accent_color": "#D8A548",
                "font_family": "Roboto, sans-serif",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ School: {school.slug}"
            )
        )

        # GradeScale is automatically created by the
        # School post_save signal in gradebook/models.py.

        # --------------------------------------------------------
        # SESSION
        # --------------------------------------------------------

        session = AcademicSession.objects.create(
            school=school,
            name="2026/2027",
            start_date=date(2026, 9, 7),
            end_date=date(2027, 7, 30),
            is_current=True,
        )

        # --------------------------------------------------------
        # TERM
        # --------------------------------------------------------

        term = Term.objects.create(
            session=session,
            name="first",
            start_date=date(2026, 9, 7),
            end_date=date(2026, 12, 18),
            next_term_begins=date(2027, 1, 11),
            is_current=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Academic session and term"
            )
        )

        # --------------------------------------------------------
        # CLASS LEVELS
        # --------------------------------------------------------

        jss1 = ClassLevel.objects.create(
            school=school,
            name="JSS1",
            order_index=1,
        )

        jss2 = ClassLevel.objects.create(
            school=school,
            name="JSS2",
            order_index=2,
        )

        # --------------------------------------------------------
        # SCHOOL ADMIN
        # --------------------------------------------------------

        admin = self.create_user(
            school=school,
            email=f"admin@{school.slug}.test",
            first_name="Grace",
            last_name="Administrator",
            role="school_admin",
            phone=f"080100{school_number:05d}",
        )

        self.create_staff_profile(
            admin,
            school,
            "School Administration",
        )

        # --------------------------------------------------------
        # TEACHERS
        # --------------------------------------------------------

        teacher1 = self.create_user(
            school=school,
            email=f"math.teacher@{school.slug}.test",
            first_name="Daniel",
            last_name="Adeyemi",
            role="teacher",
            phone=f"080200{school_number:05d}",
        )

        teacher2 = self.create_user(
            school=school,
            email=f"english.teacher@{school.slug}.test",
            first_name="Sarah",
            last_name="Okafor",
            role="teacher",
            phone=f"080300{school_number:05d}",
        )

        teacher1_profile = self.create_staff_profile(
            teacher1,
            school,
            "Mathematics",
        )

        teacher2_profile = self.create_staff_profile(
            teacher2,
            school,
            "English Language",
        )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Admin and teachers"
            )
        )

        # --------------------------------------------------------
        # CLASS ARMS
        # --------------------------------------------------------

        jss1a = ClassArm.objects.create(
            school=school,
            class_level=jss1,
            name="A",
            class_teacher=teacher1,
        )

        jss2a = ClassArm.objects.create(
            school=school,
            class_level=jss2,
            name="A",
            class_teacher=teacher2,
        )

        # --------------------------------------------------------
        # SUBJECTS
        # --------------------------------------------------------

        mathematics = Subject.objects.create(
            school=school,
            name="Mathematics",
            code="MTH",
            category="core",
            max_ca_score=40,
            max_exam_score=60,
        )

        english = Subject.objects.create(
            school=school,
            name="English Language",
            code="ENG",
            category="core",
            max_ca_score=40,
            max_exam_score=60,
        )

        science = Subject.objects.create(
            school=school,
            name="Basic Science",
            code="BSC",
            category="core",
            max_ca_score=40,
            max_exam_score=60,
        )

        computer = Subject.objects.create(
            school=school,
            name="Computer Studies",
            code="ICT",
            category="vocational",
            max_ca_score=40,
            max_exam_score=60,
        )

        subjects = [
            mathematics,
            english,
            science,
            computer,
        ]

        for subject in subjects:
            subject.class_levels.add(
                jss1,
                jss2,
            )

        # --------------------------------------------------------
        # STAFF ASSIGNMENTS
        # --------------------------------------------------------

        teacher1_profile.subjects_taught.add(
            mathematics,
            science,
        )

        teacher1_profile.assigned_classes.add(
            jss1a,
            jss2a,
        )

        teacher2_profile.subjects_taught.add(
            english,
            computer,
        )

        teacher2_profile.assigned_classes.add(
            jss1a,
            jss2a,
        )

        # --------------------------------------------------------
        # SUBJECT ASSIGNMENTS
        # --------------------------------------------------------

        assignments = [
            (
                teacher1_profile,
                mathematics,
                jss1a,
            ),
            (
                teacher1_profile,
                science,
                jss1a,
            ),
            (
                teacher2_profile,
                english,
                jss1a,
            ),
            (
                teacher2_profile,
                computer,
                jss1a,
            ),
            (
                teacher1_profile,
                mathematics,
                jss2a,
            ),
            (
                teacher2_profile,
                english,
                jss2a,
            ),
        ]

        for teacher_profile, subject, class_arm in assignments:

            SubjectAssignment.objects.create(
                school=school,
                teacher=teacher_profile,
                subject=subject,
                class_arm=class_arm,
                session=session,
                term=term,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Classes, subjects and assignments"
            )
        )

        # --------------------------------------------------------
        # STUDENTS
        # --------------------------------------------------------

        students = []
        profiles = []

        student_names = [
            ("David", "Johnson"),
            ("Amina", "Bello"),
            ("Samuel", "Okoro"),
            ("Esther", "Adekunle"),
            ("Michael", "Eze"),
        ]

        for index, (
            first_name,
            last_name,
        ) in enumerate(
            student_names,
            start=1,
        ):

            student = self.create_user(
                school=school,
                email=(
                    f"student{index}"
                    f"@{school.slug}.test"
                ),
                first_name=first_name,
                last_name=last_name,
                role="student",
            )

            # Students 1-3 -> JSS1A
            # Students 4-5 -> JSS2A

            student_class = (
                jss1a
                if index <= 3
                else jss2a
            )

            profile = StudentProfile.objects.create(
                user=student,
                school=school,
                dob=date(
                    2012 + (index % 2),
                    min(index + 1, 12),
                    10,
                ),
                gender=(
                    "female"
                    if first_name in [
                        "Amina",
                        "Esther",
                    ]
                    else "male"
                ),
                state_of_origin="Lagos",
                current_class=student_class,
                guardian_name="Pilot Guardian",
                guardian_phone=(
                    f"081000"
                    f"{school_number}"
                    f"{index:03d}"
                ),
                guardian_email=(
                    f"guardian{index}"
                    f"@{school.slug}.test"
                ),
                guardian_relationship="guardian",
            )

            students.append(student)
            profiles.append(profile)

        self.stdout.write(
            self.style.SUCCESS(
                "✓ 5 students"
            )
        )

        # --------------------------------------------------------
        # PARENTS
        # --------------------------------------------------------

        parent1 = self.create_user(
            school=school,
            email=f"parent1@{school.slug}.test",
            first_name="John",
            last_name="Guardian",
            role="parent",
            phone=f"070100{school_number:05d}",
        )

        parent2 = self.create_user(
            school=school,
            email=f"parent2@{school.slug}.test",
            first_name="Mary",
            last_name="Guardian",
            role="parent",
            phone=f"070200{school_number:05d}",
        )

        # Parent 1 -> Student 1 and Student 2

        ParentStudentLink.objects.create(
            parent=parent1,
            student=profiles[0],
            school=school,
            relationship="father",
        )

        ParentStudentLink.objects.create(
            parent=parent1,
            student=profiles[1],
            school=school,
            relationship="guardian",
        )

        # Parent 2 -> Student 3 and Student 4

        ParentStudentLink.objects.create(
            parent=parent2,
            student=profiles[2],
            school=school,
            relationship="mother",
        )

        ParentStudentLink.objects.create(
            parent=parent2,
            student=profiles[3],
            school=school,
            relationship="guardian",
        )

        # Student 5 intentionally has NO parent link.
        #
        # We will use this later to verify that parents
        # cannot access arbitrary students.

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Parents and parent/student links"
            )
        )

        # --------------------------------------------------------
        # SAMPLE SCORES
        # --------------------------------------------------------

        score_values = [
            (8, 8, 8, 4, 4, 50),
            (7, 9, 8, 5, 4, 45),
            (
                6,
                7,
                7,
                4,
                4,
                Decimal("26.50"),
            ),
            (9, 8, 9, 5, 5, 54),
            (
                5,
                6,
                7,
                4,
                4,
                Decimal("28.50"),
            ),
        ]

        for index, student in enumerate(
            students
        ):

            class_arm = (
                jss1a
                if index < 3
                else jss2a
            )

            values = score_values[index]

            ScoreEntry.objects.create(
                school=school,
                student=student,
                subject=mathematics,
                class_arm=class_arm,
                session=session,
                term=term,
                teacher=teacher1,
                first_test=Decimal(
                    str(values[0])
                ),
                second_test=Decimal(
                    str(values[1])
                ),
                assignment=Decimal(
                    str(values[2])
                ),
                project=Decimal(
                    str(values[3])
                ),
                practical=Decimal(
                    str(values[4])
                ),
                exam_score=Decimal(
                    str(values[5])
                ),
                is_published=True,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Sample results"
            )
        )

        # --------------------------------------------------------
        # ATTENDANCE
        # --------------------------------------------------------

        attendance = AttendanceSession.objects.create(
            school=school,
            class_arm=jss1a,
            teacher=teacher1,
            term=term,
            date=date(2026, 9, 18),
            mode="daily",
            is_finalized=True,
        )

        statuses = [
            "present",
            "present",
            "absent",
        ]

        for student, status in zip(
            students[:3],
            statuses,
        ):

            AttendanceRecord.objects.create(
                attendance_session=attendance,
                student=student,
                status=status,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Attendance"
            )
        )

        # --------------------------------------------------------
        # FEES
        # --------------------------------------------------------

        tuition = FeeCategory.objects.create(
            school=school,
            name="Tuition",
            description="First Term Tuition",
            is_compulsory=True,
        )

        ict_fee = FeeCategory.objects.create(
            school=school,
            name="ICT",
            description="ICT and technology fee",
            is_compulsory=True,
        )

        tuition_schedule = FeeSchedule.objects.create(
            school=school,
            term=term,
            class_level=jss1,
            fee_category=tuition,
            amount=Decimal("75000.00"),
            due_date=date(2026, 10, 1),
        )

        FeeSchedule.objects.create(
            school=school,
            term=term,
            class_level=jss1,
            fee_category=ict_fee,
            amount=Decimal("7500.00"),
            due_date=date(2026, 10, 1),
        )

        # Synthetic CASH payment only.
        #
        # This DOES NOT call Paystack.

        FeePayment.objects.create(
            school=school,
            student=profiles[0],
            fee_schedule=tuition_schedule,
            amount_paid=Decimal("25000.00"),
            payment_date=date(2026, 9, 20),
            method="cash",
            recorded_by=admin,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Fees and synthetic payment"
            )
        )

        # --------------------------------------------------------
        # CBT TOPIC
        # --------------------------------------------------------

        topic = Topic.objects.create(
            school=school,
            subject=mathematics,
            class_level=jss1,
            name="Basic Arithmetic",
        )

        # --------------------------------------------------------
        # CBT QUESTIONS
        # --------------------------------------------------------

        question_data = [
            (
                "What is 5 + 7?",
                [
                    {
                        "id": "A",
                        "text": "10",
                    },
                    {
                        "id": "B",
                        "text": "12",
                    },
                    {
                        "id": "C",
                        "text": "14",
                    },
                    {
                        "id": "D",
                        "text": "15",
                    },
                ],
                "B",
            ),
            (
                "What is 9 × 3?",
                [
                    {
                        "id": "A",
                        "text": "18",
                    },
                    {
                        "id": "B",
                        "text": "21",
                    },
                    {
                        "id": "C",
                        "text": "27",
                    },
                    {
                        "id": "D",
                        "text": "36",
                    },
                ],
                "C",
            ),
            (
                "What is 20 ÷ 4?",
                [
                    {
                        "id": "A",
                        "text": "4",
                    },
                    {
                        "id": "B",
                        "text": "5",
                    },
                    {
                        "id": "C",
                        "text": "6",
                    },
                    {
                        "id": "D",
                        "text": "8",
                    },
                ],
                "B",
            ),
            (
                "What is 15 - 6?",
                [
                    {
                        "id": "A",
                        "text": "7",
                    },
                    {
                        "id": "B",
                        "text": "8",
                    },
                    {
                        "id": "C",
                        "text": "9",
                    },
                    {
                        "id": "D",
                        "text": "10",
                    },
                ],
                "C",
            ),
            (
                "What is 4 squared?",
                [
                    {
                        "id": "A",
                        "text": "8",
                    },
                    {
                        "id": "B",
                        "text": "12",
                    },
                    {
                        "id": "C",
                        "text": "16",
                    },
                    {
                        "id": "D",
                        "text": "20",
                    },
                ],
                "C",
            ),
        ]

        questions = []

        for (
            question_text,
            options,
            answer,
        ) in question_data:

            question = Question.objects.create(
                school=school,
                subject=mathematics,
                topic=topic,
                class_level=jss1,
                question_text=question_text,
                question_type="mcq",
                difficulty="easy",
                cognitive_level="knowledge",
                options=options,
                correct_answer=answer,
                created_by=teacher1,
                is_active=True,
            )

            questions.append(question)

        # --------------------------------------------------------
        # CBT EXAM
        # --------------------------------------------------------

        now = timezone.now()

        exam = CBTExam.objects.create(
            school=school,
            title="Pilot Mathematics Test",
            subject=mathematics,
            term=term,
            session=session,
            created_by=teacher1,
            start_datetime=(
                now - timedelta(hours=1)
            ),
            end_datetime=(
                now + timedelta(days=7)
            ),
            duration_minutes=20,
            instructions=(
                "Synthetic pilot examination. "
                "Answer all questions."
            ),
            selection_mode="manual",
            randomize_questions=False,
            randomize_options=False,
            allow_review=True,
            show_score_immediately=True,
            status="published",
        )

        exam.class_arms.add(jss1a)

        exam.manual_questions.add(
            *questions
        )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ CBT exam and questions"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ {school.name} complete"
            )
        )

        return {
            "school": school,
            "admin": admin,
            "teachers": [
                teacher1,
                teacher2,
            ],
            "students": students,
            "parents": [
                parent1,
                parent2,
            ],
            "session": session,
            "term": term,
            "classes": [
                jss1a,
                jss2a,
            ],
            "subjects": subjects,
            "exam": exam,
        }

    # ============================================================
    # FINAL VERIFICATION
    # ============================================================

    def print_summary(
        self,
        created_data,
    ):

        self.stdout.write("")
        self.stdout.write(
            "=" * 60
        )

        self.stdout.write(
            self.style.SUCCESS(
                "PAIDEIA PILOT DATA CREATED SUCCESSFULLY"
            )
        )

        self.stdout.write(
            "=" * 60
        )

        for slug, data in created_data.items():

            school = data["school"]

            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    school.name
                )
            )

            self.stdout.write(
                f"Slug: {school.slug}"
            )

            self.stdout.write(
                f"Plan: {school.subscription_plan}"
            )

            self.stdout.write(
                "Users: "
                f"{User.objects.filter(school=school).count()}"
            )

            self.stdout.write(
                "Students: "
                f"{StudentProfile.objects.filter(school=school).count()}"
            )

            self.stdout.write(
                "Staff: "
                f"{StaffProfile.objects.filter(school=school).count()}"
            )

            self.stdout.write(
                "Parent links: "
                f"{ParentStudentLink.objects.filter(school=school).count()}"
            )

            self.stdout.write(
                "Scores: "
                f"{ScoreEntry.objects.filter(school=school).count()}"
            )

            self.stdout.write(
                "Fee schedules: "
                f"{FeeSchedule.objects.filter(school=school).count()}"
            )

            self.stdout.write(
                "Payments: "
                f"{FeePayment.objects.filter(school=school).count()}"
            )

            self.stdout.write(
                "CBT questions: "
                f"{Question.objects.filter(school=school).count()}"
            )

        # --------------------------------------------------------
        # LOGIN DETAILS
        # --------------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            "=" * 60
        )

        self.stdout.write(
            self.style.WARNING(
                "TEST LOGIN DETAILS"
            )
        )

        self.stdout.write(
            "=" * 60
        )

        self.stdout.write("")
        self.stdout.write(
            f"Password for ALL test accounts: {self.TEST_PASSWORD}"
        )

        for school_data in self.SCHOOLS:

            slug = school_data["slug"]

            self.stdout.write("")
            self.stdout.write(
                school_data["name"]
            )

            self.stdout.write(
                f"  Admin: admin@{slug}.test"
            )

            self.stdout.write(
                f"  Math teacher: math.teacher@{slug}.test"
            )

            self.stdout.write(
                f"  English teacher: english.teacher@{slug}.test"
            )

            self.stdout.write(
                f"  Student: student1@{slug}.test"
            )

            self.stdout.write(
                f"  Parent: parent1@{slug}.test"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "5 pilot schools successfully created."
            )
        )

        self.stdout.write(
            self.style.WARNING(
                "These accounts contain synthetic test data only."
            )
        )