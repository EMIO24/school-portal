from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from accounts.models import CustomUser
from .models import School, PlatformSecurity, PlatformEvent
from .plans import PLAN_FEATURES, calculate_billing_snapshot, entitlements, required_feature

class PlansBrandingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.school = School.objects.create(name='Design School', subdomain='design', slug='design', subscription_plan='basic')
        self.admin = CustomUser.objects.create_user('admin@design.test','Password!123',school=self.school,role='school_admin', must_change_password=False)
        self.owner = CustomUser.objects.create_superuser('owner@design.test','Password!123')
        self.client = APIClient(HTTP_X_SCHOOL_SLUG='design')
        self.client.force_authenticate(self.admin)
    def test_basic_cannot_call_premium_api_directly(self):
        for path in ['/api/cbt/topics/', '/api/analytics/overview/', '/api/notifications/', '/api/students/bulk-import/', '/api/staff/bulk-import/', '/api/promotion/', '/api/scratch-cards/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code,403,path)
            self.assertEqual(response.json()['code'],'plan_feature_required')
    def test_plan_change_takes_effect_without_reissuing_token(self):
        self.assertEqual(self.client.get('/api/cbt/topics/').status_code,403)
        self.school.subscription_plan='premium';self.school.save()
        self.assertEqual(self.client.get('/api/cbt/topics/').status_code,200)
        self.school.subscription_plan='basic';self.school.save()
        self.assertEqual(self.client.get('/api/cbt/topics/').status_code,403)
    def test_free_setup_keeps_billing_but_blocks_operational_features(self):
        self.school.subscription_plan='free';self.school.save()
        self.assertEqual(self.client.get('/api/fees/subscription/').status_code,200)
        self.assertEqual(self.client.get('/api/fees/categories/').status_code,403)
        self.assertEqual(self.client.get('/api/parent/dashboard/1/').status_code,403)
        self.assertEqual(self.client.get('/api/class-levels/').status_code,200)
    def test_missing_tenant_cannot_bypass_feature_checks(self):
        client=APIClient();client.force_authenticate(self.admin)
        self.assertEqual(client.get('/api/cbt/topics/').status_code,404)
    def test_owner_can_assign_all_five_layouts_even_when_school_suspended(self):
        self.school.is_active=False;self.school.save()
        self.client.force_authenticate(self.owner)
        for layout in ['scholar','campus','studio','executive','heritage']:
            response=self.client.patch('/api/platform/schools/%s/'%self.school.pk, {'theme_config':{'layout':layout,'primary_color':'#123456','secondary_color':'#234567','accent_color':'#CCAA55','font_family':'Georgia, serif'},'subscription_plan':'premium'},format='json')
            self.assertEqual(response.status_code,200,response.data)
            self.school.refresh_from_db();self.assertEqual(self.school.get_theme()['layout'],layout)
        self.assertEqual(PlatformEvent.objects.filter(action='school.updated').count(),5)
    def test_nonowner_and_viewer_cannot_assign_branding(self):
        url='/api/platform/schools/%s/'%self.school.pk
        self.assertEqual(self.client.patch(url,{'theme_config':{'layout':'studio'}},format='json').status_code,403)
        PlatformSecurity.objects.create(user=self.owner,access_level='viewer')
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(url,{'theme_config':{'layout':'studio'}},format='json').status_code,403)
        self.assertEqual(self.client.get('/api/platform/appearance/').status_code,403)
    def test_invalid_css_values_and_unknown_layout_rejected(self):
        self.client.force_authenticate(self.owner)
        for config in [{'layout':'unknown'}, {'primary_color':'red; background:url(test)'}, {'font_family':'url(test)'}, ['not an object']]:
            response=self.client.patch('/api/platform/schools/%s/'%self.school.pk,{'theme_config':config},format='json')
            self.assertEqual(response.status_code,400)
    def test_branding_and_features_are_school_specific(self):
        self.school.theme_config={'layout':'campus','primary_color':'#126633'};self.school.save()
        other=School.objects.create(name='Other',slug='other-design',subdomain='other-design',subscription_plan='premium',theme_config={'layout':'heritage'})
        first=self.client.get('/api/school/me/').json()
        second=self.client.get('/api/school/me/',HTTP_X_SCHOOL_SLUG='other-design').json()
        self.assertEqual(first['theme']['layout'],'campus');self.assertEqual(second['theme']['layout'],'heritage')
        self.assertNotIn('cbt',first['entitlements']['features']);self.assertIn('cbt',second['entitlements']['features'])
    def test_billing_callback_and_receipts_are_not_plan_gated(self):
        for path in ['/api/fees/subscription/','/api/fees/pay/verify/','/api/fees/receipts/123/','/api/platform/paystack/webhook/']:
            self.assertIsNone(required_feature(path))
    def test_catalog_has_all_plans(self):
        self.client.force_authenticate(self.owner)
        response=self.client.get('/api/platform/appearance/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['plans'],PLAN_FEATURES)

    def test_billing_rates_and_discount_boundaries(self):
        from academics.models import AcademicSession, Term

        session = AcademicSession.objects.create(
            school=self.school,
            name='2026/2027',
            start_date='2026-09-01',
            end_date='2027-07-30',
            is_current=True,
        )
        term = Term.objects.create(
            session=session,
            name='first',
            start_date='2026-09-01',
            end_date='2026-12-18',
            is_current=True,
        )

        plan_rates = {
            'basic': {
                98: {'final': 98 * 800, 'unit_price': 800},
                99: {'final': 99 * 800, 'unit_price': 800},
                100: {'final': 100 * 720, 'unit_price': 720},
                101: {'final': 101 * 720, 'unit_price': 720},
                500: {'final': 500 * 720, 'unit_price': 720},
            },
            'premium': {
                98: {'final': 98 * 1500, 'unit_price': 1500},
                99: {'final': 99 * 1500, 'unit_price': 1500},
                100: {'final': 100 * 1350, 'unit_price': 1350},
                101: {'final': 101 * 1350, 'unit_price': 1350},
                500: {'final': 500 * 1350, 'unit_price': 1350},
            },
            'enterprise': {
                98: {'final': 98 * 2500, 'unit_price': 2500},
                99: {'final': 99 * 2500, 'unit_price': 2500},
                100: {'final': 100 * 2250, 'unit_price': 2250},
                101: {'final': 101 * 2250, 'unit_price': 2250},
                500: {'final': 500 * 2250, 'unit_price': 2250},
            },
        }

        for plan_code, values in plan_rates.items():
            for active_students, expected in values.items():
                snapshot = calculate_billing_snapshot(
                    school=self.school,
                    session=session,
                    term=term,
                    plan_code=plan_code,
                    active_student_count=active_students,
                )
                self.assertEqual(snapshot['plan_code'], plan_code)
                self.assertEqual(snapshot['active_student_count'], active_students)
                self.assertEqual(snapshot['final_amount'], float(expected['final']))
                self.assertEqual(snapshot['unit_price'], float(expected['unit_price']))
                self.assertEqual(snapshot['discount_percentage'], 10 if active_students >= 100 else 0)
                self.assertEqual(snapshot['discount_eligible'], active_students >= 100)

    def test_plan_catalog_enforces_basic_premium_enterprise_entitlements(self):
        self.assertNotIn('cbt', PLAN_FEATURES['basic'])
        self.assertNotIn('notifications', PLAN_FEATURES['basic'])
        self.assertIn('cbt', PLAN_FEATURES['premium'])
        self.assertIn('notifications', PLAN_FEATURES['premium'])
        self.assertIn('analytics', PLAN_FEATURES['premium'])
        self.assertIn('multi_campus', PLAN_FEATURES['enterprise'])
        self.assertIn('custom_workflows', PLAN_FEATURES['enterprise'])
        self.assertNotIn('multi_campus', PLAN_FEATURES['premium'])
        self.assertNotIn('custom_workflows', PLAN_FEATURES['premium'])

    def test_setup_status_reports_basic_readiness(self):
        from academics.models import AcademicSession, Term
        from enrollment.models import ClassLevel, Subject

        session = AcademicSession.objects.create(
            school=self.school,
            name='2026/2027',
            start_date='2026-09-01',
            end_date='2027-07-30',
            is_current=True,
        )
        Term.objects.create(
            session=session,
            name='first',
            start_date='2026-09-01',
            end_date='2026-12-18',
            is_current=True,
        )
        ClassLevel.objects.create(school=self.school, name='JSS1', order_index=1)
        Subject.objects.create(school=self.school, name='Mathematics', code='MTH')

        response = self.client.get('/api/school/setup-status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['plan'], 'basic')
        self.assertTrue(response.data['basic_setup_ready'])
        self.assertTrue(response.data['wizard_ready'])
        self.assertGreaterEqual(response.data['readiness'], 75)
        self.assertEqual(len(response.data['steps']), 8)
        self.assertEqual(response.data['steps'][0]['key'], 'academic_session')
        self.assertEqual(response.data['steps'][-1]['key'], 'grading_system')

    def test_result_design_defaults_and_layout_validation(self):
        theme = self.school.get_theme()
        self.assertEqual(theme['result_layout'], 'classic')
        self.assertIn('summary', theme['result_sections'])
        self.assertIn('scores', theme['result_sections'])

        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            f'/api/platform/schools/{self.school.pk}/',
            {'theme_config': {
                'layout': 'campus',
                'result_layout': 'modern',
                'result_sections': ['summary', 'scores', 'attendance', 'remarks'],
            }},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.school.refresh_from_db()
        self.assertEqual(self.school.get_theme()['result_layout'], 'modern')
        self.assertEqual(self.school.get_theme()['result_sections'], ['summary', 'scores', 'attendance', 'remarks'])

        invalid = self.client.patch(
            f'/api/platform/schools/{self.school.pk}/',
            {'theme_config': {'result_layout': 'outlandish'}},
            format='json',
        )
        self.assertEqual(invalid.status_code, 400)

    def test_enterprise_plan_is_included_in_entitlements(self):
        self.school.subscription_plan = 'enterprise'
        self.school.save()
        entitlements_data = entitlements(self.school)
        self.assertEqual(entitlements_data['plan'], 'enterprise')
        self.assertIn('cbt', entitlements_data['features'])
        self.assertIn('analytics', entitlements_data['features'])
        self.assertIn('custom_workflows', entitlements_data['features'])
