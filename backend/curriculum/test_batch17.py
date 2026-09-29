from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from academics.models import AcademicSession
from curriculum.models import (
    AcademicStandardTopic,
    CurriculumApplicability,
    CurriculumSource,
    CurriculumVersion,
    SchoolAcademicStandard,
)
from enrollment.models import ClassLevel, Subject
from tenants.models import School


class Batch17AcademicStandardModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Continuity Academy', slug='continuity-academy')
        self.other_school = School.objects.create(name='Other Academy', slug='other-academy')
        self.level = ClassLevel.objects.create(school=self.school, name='JSS 1', order=1)
        self.other_level = ClassLevel.objects.create(school=self.other_school, name='JSS 1', order=1)
        self.subject = Subject.objects.create(school=self.school, name='Mathematics', code='MATH')
        self.other_subject = Subject.objects.create(school=self.other_school, name='Mathematics', code='MATH')
        self.session = AcademicSession.objects.create(
            school=self.school, name='2026/2027', start_date=date(2026, 9, 1), end_date=date(2027, 7, 31)
        )
        self.source = CurriculumSource.objects.create(
            school=self.school, name='Recorded Mathematics Curriculum', kind=CurriculumSource.Kind.GOVERNMENT,
            jurisdiction='Recorded jurisdiction'
        )
        self.version = CurriculumVersion.objects.create(source=self.source, label='2026 edition')

    def test_applicability_pins_one_version_to_session_class_subject(self):
        row = CurriculumApplicability(
            school=self.school, session=self.session, class_level=self.level,
            subject=self.subject, curriculum_version=self.version,
        )
        row.full_clean()
        row.save()
        self.assertEqual(row.curriculum_version, self.version)

        duplicate = CurriculumApplicability(
            school=self.school, session=self.session, class_level=self.level,
            subject=self.subject, curriculum_version=self.version,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_applicability_rejects_cross_tenant_scope(self):
        row = CurriculumApplicability(
            school=self.school, session=self.session, class_level=self.other_level,
            subject=self.subject, curriculum_version=self.version,
        )
        with self.assertRaises(ValidationError) as error:
            row.full_clean()
        self.assertIn('class_level', error.exception.message_dict)

    def test_standard_keeps_required_and_school_enrichment_distinct(self):
        standard = SchoolAcademicStandard.objects.create(
            school=self.school, curriculum_version=self.version, class_level=self.level,
            subject=self.subject, title='JSS 1 Mathematics Standard',
        )
        required = AcademicStandardTopic.objects.create(
            standard=standard, term='first', title='Whole Numbers', position=1,
            requirement=AcademicStandardTopic.Requirement.REQUIRED,
        )
        enrichment = AcademicStandardTopic.objects.create(
            standard=standard, term='first', title='Mathematical Reasoning Lab', position=2,
            requirement=AcademicStandardTopic.Requirement.ENRICHMENT,
        )
        self.assertEqual(required.requirement, 'required')
        self.assertEqual(enrichment.requirement, 'enrichment')

    def test_new_revision_can_supersede_without_mutating_approved_history(self):
        first = SchoolAcademicStandard.objects.create(
            school=self.school, curriculum_version=self.version, class_level=self.level,
            subject=self.subject, title='JSS 1 Mathematics Standard', revision=1,
            status=SchoolAcademicStandard.Status.APPROVED,
        )
        second = SchoolAcademicStandard(
            school=self.school, curriculum_version=self.version, class_level=self.level,
            subject=self.subject, title='JSS 1 Mathematics Standard', revision=2,
            supersedes=first,
        )
        second.full_clean()
        second.save()
        first.refresh_from_db()
        self.assertEqual(first.status, SchoolAcademicStandard.Status.APPROVED)
        self.assertEqual(second.supersedes_id, first.pk)

    def test_standard_rejects_cross_tenant_curriculum_version(self):
        other_source = CurriculumSource.objects.create(
            school=self.other_school, name='Other Curriculum', kind=CurriculumSource.Kind.SCHOOL
        )
        other_version = CurriculumVersion.objects.create(source=other_source, label='v1')
        standard = SchoolAcademicStandard(
            school=self.school, curriculum_version=other_version, class_level=self.level,
            subject=self.subject, title='Invalid Standard',
        )
        with self.assertRaises(ValidationError) as error:
            standard.full_clean()
        self.assertIn('curriculum_version', error.exception.message_dict)
