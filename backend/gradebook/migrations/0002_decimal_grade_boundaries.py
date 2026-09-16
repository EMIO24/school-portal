from decimal import Decimal
from django.db import migrations

def forward(apps, schema_editor):
    GradeScale = apps.get_model('gradebook','GradeScale')
    for lower, upper in [(70,74),(65,69),(60,64),(55,59),(50,54),(45,49),(40,44),(0,39)]:
        GradeScale.objects.filter(min_score=lower,max_score=upper).update(max_score=Decimal(upper)+Decimal('0.99'))

class Migration(migrations.Migration):
    dependencies = [('gradebook','0001_initial')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
