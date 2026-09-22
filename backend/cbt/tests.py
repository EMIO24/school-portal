from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from io import BytesIO
from PIL import Image
from tempfile import TemporaryDirectory
from rest_framework.test import APIClient

from accounts.models import CustomUser
from tenants.models import School


class QuestionImageUploadTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='CBT School', slug='cbt-school', subdomain='cbt-school', subscription_plan='premium')
        self.admin = CustomUser.objects.create_user('admin@cbt.test', 'Password!123', school=self.school, role='school_admin')
        self.client = APIClient()
        self.headers = {'HTTP_X_SCHOOL_SLUG': 'cbt-school'}

    def image(self):
        output = BytesIO(); Image.new('RGB', (20, 20), 'white').save(output, 'PNG')
        return SimpleUploadedFile('diagram.png', output.getvalue(), content_type='image/png')

    def test_authorized_image_upload_uses_tenant_folder(self):
        self.client.force_authenticate(self.admin)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory, MEDIA_URL='/media/'):
            response = self.client.post('/api/cbt/questions/image/', {'image': self.image()}, format='multipart', **self.headers)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['url'].startswith('/media/question-images/%s/' % self.school.pk))

    def test_anonymous_image_upload_is_denied(self):
        response = self.client.post('/api/cbt/questions/image/', {'image': self.image()}, format='multipart', **self.headers)
        self.assertIn(response.status_code, (401, 403))

# Create your tests here.
