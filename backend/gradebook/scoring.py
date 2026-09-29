"""Term-scoped scoring rules and Decimal calculations, shared by all writers."""
from decimal import Decimal
from rest_framework import serializers
from .models import GradeScale, TermScoring

LEGACY_COMPONENTS = [
    {'key':key, 'name':name, 'maximum':str(maximum), 'kind':kind}
    for key,name,maximum,kind in [('first_test','1st Test',10,'assessment'),('second_test','2nd Test',10,'assessment'),
        ('assignment','Assignment',10,'assessment'),('project','Project',5,'assessment'),
        ('practical','Practical',5,'assessment'),('exam_score','Exam',60,'exam')]
]

class ComponentInput(serializers.Serializer):
    key = serializers.RegexField(r'^[a-z][a-z0-9_]{0,31}$')
    name = serializers.CharField(max_length=60)
    maximum = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0.01'), max_value=Decimal("100"))
    kind = serializers.ChoiceField(choices=['assessment','exam'], default='assessment')

    def validate_key(self, value):
        if value in {'id','student','policy','grade','remark','review_state','is_published','total_score','ca_total','constructor','prototype'}:
            raise serializers.ValidationError('Choose a distinct assessment key, separate from result fields.')
        return value

class BandInput(serializers.Serializer):
    grade = serializers.CharField(max_length=2)
    remark = serializers.CharField(max_length=20)
    min_score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"))
    max_score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"))

class ScoringInput(serializers.Serializer):
    components = ComponentInput(many=True, allow_empty=False)
    bands = BandInput(many=True, allow_empty=False)

    def validate_components(self, rows):
        if len(rows) > 12:
            raise serializers.ValidationError('Use at most 12 assessment components.')
        if len({r['key'] for r in rows}) != len(rows) or len({r['name'].casefold() for r in rows}) != len(rows):
            raise serializers.ValidationError('Each assessment must have a unique name and key.')
        total = sum(r['maximum'] for r in rows)
        if total != 100:
            raise serializers.ValidationError(f'Assessment components total {total}. The total must equal 100.')
        return rows

    def validate_bands(self, rows):
        if len(rows)>20 or len({r['grade'].casefold() for r in rows}) != len(rows):
            raise serializers.ValidationError('Use distinct grades, with at most 20 ranges.')
        expected = Decimal('0')
        for row in sorted(rows,key=lambda r:r['min_score']):
            if row['min_score'] > row['max_score'] or row['min_score'] != expected:
                raise serializers.ValidationError('Grade ranges must cover 0 to 100 without overlaps, reversed ranges or gaps (use two decimal places).')
            expected = row['max_score'] + Decimal('0.01')
        if expected != Decimal('100.01'):
            raise serializers.ValidationError('Grade ranges must cover every score from 0 to 100.')
        return rows

def defaults(school):
    return {'components':LEGACY_COMPONENTS, 'bands':[
        {'grade':b.grade,'remark':b.remark,'min_score':str(b.min_score),'max_score':str(b.max_score)}
        for b in GradeScale.objects.filter(school=school).order_by('min_score')]}

def json_values(data):
    if isinstance(data,Decimal): return str(data)
    if isinstance(data,list): return [json_values(x) for x in data]
    if isinstance(data,dict): return {k:json_values(v) for k,v in data.items()}
    return data

def policy_for(school,term,create=False):
    policy = TermScoring.objects.filter(school=school,term=term).first()
    if not policy and create:
        form = ScoringInput(data=defaults(school)); form.is_valid(raise_exception=True)
        policy = TermScoring.objects.create(school=school,term=term,**json_values(form.validated_data))
    return policy

def checked_scores(policy, values, complete=False):
    if not isinstance(values,dict): raise serializers.ValidationError('Enter assessment scores by component.')
    components = {c['key']:c for c in policy.components}
    if set(values)-set(components): raise serializers.ValidationError('Scores contain an assessment that is not configured for this term.')
    result = {}
    field = serializers.DecimalField(max_digits=5,decimal_places=2,min_value=Decimal("0"))
    for key,component in components.items():
        value = values.get(key)
        if value is None or value == '':
            if complete: raise serializers.ValidationError(f"Missing score for {component['name']}. Enter a score, including zero where appropriate.")
            result[key] = None
            continue
        number = field.run_validation(value)
        if number > Decimal(component['maximum']):
            raise serializers.ValidationError(f"{component['name']} cannot exceed {component['maximum']} marks.")
        result[key] = str(number)
    return result

def calculate(policy, values):
    values = checked_scores(policy,values)
    total = sum((Decimal(v) for v in values.values() if v is not None),Decimal('0'))
    if any(v is None for v in values.values()): return total,'',''
    grade, remark = grade_for(total, policy.bands)
    return total, grade, remark


def grade_for(total, bands):
    for band in bands:
        if Decimal(band['min_score']) <= total <= Decimal(band['max_score']):
            return band['grade'], band['remark']
    raise serializers.ValidationError('No grade covers this score. Ask the administrator to review the grading configuration.')

def entry_components(entry):
    components = entry.policy.components if entry.policy_id else LEGACY_COMPONENTS
    return [{**c,'score':entry.component_scores.get(c['key']) if entry.policy_id else str(getattr(entry,c['key']))} for c in components]
