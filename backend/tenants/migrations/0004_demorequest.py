from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('tenants', '0003_platformsecurity_platformevent')]

    operations = [
        migrations.CreateModel(
            name='DemoRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_name', models.CharField(max_length=255)),
                ('contact_name', models.CharField(max_length=150)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=30)),
                ('student_population', models.PositiveIntegerField()),
                ('location', models.CharField(max_length=255)),
                ('message', models.TextField(blank=True, max_length=2000)),
                ('status', models.CharField(choices=[('new', 'New'), ('contacted', 'Contacted')], default='new', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
    ]
