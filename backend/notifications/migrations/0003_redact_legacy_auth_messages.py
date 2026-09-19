from django.db import migrations

def redact(apps, schema_editor):
    apps.get_model('notifications','NotificationLog').objects.filter(message_body__icontains='login code is').update(message_body='Authentication message redacted.',error_message='')

class Migration(migrations.Migration):
    dependencies = [('notifications','0002_notificationbatch_notificationoutbox_and_more')]
    operations = [migrations.RunPython(redact, migrations.RunPython.noop)]
