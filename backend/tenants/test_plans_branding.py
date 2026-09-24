from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from accounts.models import CustomUser
from .models import School, PlatformSecurity, PlatformEvent
from .plans import PLAN_FEATURES, required_feature

class PlansBrandingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.school = School.objects.create(name='Design School', subdomain='design', slug='design', subscription_plan='basic')
        self.admin = CustomUser.objects.create_user('admin@design.test','Password!123',school=self.school,role='school_admin', must_change_password=False)
        self.owner = CustomUser.objects.create_superuser('owner@design.test','Password!123')
        self.client = APIClient(HTTP_X_SCHOOL_SLUG='design')
        self.client.force_authenticate(self.admin)
    def test_basic_cannot_call_premium_api_directly(self):
        for path in ['/api/cbt/topics/', '/api/analytics/overview/', '/api/promotion/', '/api/scratch-cards/']:
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
