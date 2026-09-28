import os
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser, ParentStudentLink
from academics.models import AcademicSession, Term
from enrollment.models import (
    ClassArm,
    ClassLevel,
    StaffProfile,
    StudentProfile,
    Subject,
    SubjectAssignment,
)
from fees.models import FeeCategory, FeePayment, FeeSchedule, SchoolPaymentAccount
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
            existing.delete()

        school = School.objects.create(
            name="Greenfield International Academy",
            slug=DEMO_SLUG,
            subdomain=DEMO_SLUG,
            logo="https://placehold.co/512x512/173B56/FFFFFF.png?text=GIA",
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
