from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from academics.models import AcademicSession, Term
from curriculum.models import (
    AcademicStandardTopic,
    CurriculumApplicability,
    CurriculumSource,
    CurriculumVersion,
    SchoolAcademicStandard,
)
from enrollment.models import ClassLevel, Subject
from tenants.models import School
from enrollment import test_operations as operations
from curriculum.models import CurriculumPlan


class Batch17AcademicStandardModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Continuity Academy', slug='continuity-academy')
        self.other_school = School.objects.create(name='Other Academy', slug='other-academy')
        self.level = ClassLevel.objects.create(school=self.school, name='JSS1', order_index=1)
        self.other_level = ClassLevel.objects.create(school=self.other_school, name='JSS1', order_index=1)
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


class Batch17AcademicStandardAPITests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def create_source_version(self):
        source = self.client.post('/api/curriculum/standards/sources/', {
            'name': 'Recorded National Mathematics Curriculum',
            'kind': 'government',
            'jurisdiction': 'Recorded jurisdiction',
            'authority': 'Recorded authority',
        }, format='json')
        self.assertEqual(source.status_code, 201, source.data)
        source_id = source.data['source']['id']
        version = self.client.post(f'/api/curriculum/standards/sources/{source_id}/versions/', {
            'label': '2026 edition',
            'reference': 'Recorded reference',
        }, format='json')
        self.assertEqual(version.status_code, 201, version.data)
        return source_id, CurriculumVersion.objects.get(source_id=source_id, label='2026 edition')

    def create_standard(self, version):
        response = self.client.post('/api/curriculum/standards/', {
            'class_level': self.level.pk,
            'subject': self.subject.pk,
            'curriculum_version': version.pk,
            'title': 'JSS1 Mathematics Academic Standard',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['standard']['id']

    def add_topic(self, standard, title='Whole Numbers', week=2, position=1):
        response = self.client.post(f'/api/curriculum/standards/{standard}/topics/', {
            'term': 'first',
            'title': title,
            'position': position,
            'recommended_week': week,
            'requirement': 'required',
            'objectives': ['Explain the concept', 'Apply the concept'],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['topic']

    def transition(self, standard, action):
        return self.client.post(
            f'/api/curriculum/standards/{standard}/transition/', {'action': action}, format='json'
        )

    def test_full_standard_lifecycle_generation_and_no_overwrite(self):
        _, version = self.create_source_version()
        applicability = self.client.put('/api/curriculum/standards/applicability/', {
            'session': self.session.pk, 'class_level': self.level.pk,
            'subject': self.subject.pk, 'curriculum_version': version.pk,
        }, format='json')
        self.assertEqual(applicability.status_code, 200, applicability.data)

        standard = self.create_standard(version)
        self.add_topic(standard)

        self.assertEqual(self.transition(standard, 'review').status_code, 409)
        self.assertEqual(self.transition(standard, 'submit').status_code, 200)
        self.assertEqual(self.transition(standard, 'review').status_code, 200)
        approved = self.transition(standard, 'approve')
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data['standard']['status'], 'approved')

        self.assertEqual(
            self.client.post(f'/api/curriculum/standards/{standard}/topics/', {
                'term': 'first', 'title': 'Late mutation', 'position': 2, 'recommended_week': 3
            }, format='json').status_code,
            409,
        )

        generated = self.client.post(
            f'/api/curriculum/standards/{standard}/generate-plan/', {'term': self.term.pk}, format='json'
        )
        self.assertEqual(generated.status_code, 201, generated.data)
        plan = CurriculumPlan.objects.get(pk=generated.data['plan'])
        self.assertEqual(plan.weeks.get(number=2).topics.get().title, 'Whole Numbers')
        self.assertEqual(
            list(plan.weeks.get(number=2).topics.get().objectives.values_list('text', flat=True)),
            ['Explain the concept', 'Apply the concept'],
        )
        self.assertEqual(
            self.client.post(
                f'/api/curriculum/standards/{standard}/generate-plan/', {'term': self.term.pk}, format='json'
            ).status_code,
            409,
        )

    def test_applicability_cannot_change_after_term_execution_exists(self):
        _, version = self.create_source_version()
        source2 = CurriculumSource.objects.create(school=self.school, name='Second recorded source', kind='other')
        version2 = CurriculumVersion.objects.create(source=source2, label='v2')
        payload = {
            'session': self.session.pk, 'class_level': self.level.pk,
            'subject': self.subject.pk, 'curriculum_version': version.pk,
        }
        self.assertEqual(self.client.put('/api/curriculum/standards/applicability/', payload, format='json').status_code, 200)
        CurriculumPlan.objects.create(school=self.school, term=self.term, class_level=self.level, subject=self.subject)
        payload['curriculum_version'] = version2.pk
        response = self.client.put('/api/curriculum/standards/applicability/', payload, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            CurriculumApplicability.objects.get(
                school=self.school, session=self.session, class_level=self.level, subject=self.subject
            ).curriculum_version_id,
            version.pk,
        )

    def test_approved_standard_revision_clones_content_and_preserves_history(self):
        _, version = self.create_source_version()
        standard = self.create_standard(version)
        self.add_topic(standard)
        for action in ('submit', 'review', 'approve'):
            self.assertEqual(self.transition(standard, action).status_code, 200)

        revised = self.client.post(f'/api/curriculum/standards/{standard}/revise/', {}, format='json')
        self.assertEqual(revised.status_code, 201, revised.data)
        self.assertEqual(revised.data['standard']['revision'], 2)
        self.assertEqual(revised.data['standard']['status'], 'draft')
        self.assertEqual(revised.data['standard']['supersedes'], standard)
        self.assertEqual(revised.data['standard']['topics'][0]['title'], 'Whole Numbers')
        self.assertEqual(SchoolAcademicStandard.objects.get(pk=standard).status, 'approved')
        self.assertEqual(self.client.post(f'/api/curriculum/standards/{standard}/revise/', {}, format='json').status_code, 409)

    def test_teacher_sees_only_approved_assigned_standard(self):
        _, version = self.create_source_version()
        standard = self.create_standard(version)
        self.add_topic(standard)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get('/api/curriculum/standards/').data['standards'], [])
        self.assertEqual(self.client.get(f'/api/curriculum/standards/{standard}/').status_code, 404)

        self.client.force_authenticate(self.admin)
        for action in ('submit', 'review', 'approve'):
            self.assertEqual(self.transition(standard, action).status_code, 200)

        self.client.force_authenticate(self.teacher)
        listing = self.client.get('/api/curriculum/standards/')
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([row['id'] for row in listing.data['standards']], [standard])
        self.assertEqual(self.client.get(f'/api/curriculum/standards/{standard}/').status_code, 200)

    def test_foreign_tenant_records_are_never_accepted(self):
        foreign_source = CurriculumSource.objects.create(school=self.other, name='Foreign source', kind='other')
        foreign_version = CurriculumVersion.objects.create(source=foreign_source, label='foreign-v1')
        response = self.client.post('/api/curriculum/standards/', {
            'class_level': self.level.pk, 'subject': self.subject.pk,
            'curriculum_version': foreign_version.pk, 'title': 'Invalid',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SchoolAcademicStandard.objects.filter(title='Invalid').exists())
