from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0010_batch20_migration_command_centre"),
    ]

    operations = [
        migrations.AddField(
            model_name="migrationconflict",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="migrationconflict",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
