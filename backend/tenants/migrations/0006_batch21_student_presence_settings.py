from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0005_alter_school_subscription_plan"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="arrival_cutoff_time",
            field=models.TimeField(
                blank=True,
                null=True,
                help_text="Optional daily arrival deadline used for lateness evidence.",
            ),
        ),
        migrations.AddField(
            model_name="school",
            name="student_clockout_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Enable optional student departure recording.",
            ),
        ),
    ]
