"""One feature catalog for API enforcement and portal presentation."""
from decimal import Decimal

FEATURES = {
    'core': 'School setup, people and academic calendar',
    'attendance': 'Attendance tracking',
    'results': 'Scores and report cards',
    'fees': 'School fees and PDF receipts',
    'timetable': 'Timetable builder',
    'notifications': 'Email and SMS tools',
    'cbt': 'Computer-Based Testing',
    'analytics': 'Advanced performance analytics',
    'bulk_import': 'Bulk student and staff imports',
    'promotion': 'Student promotion workflows',
    'scratch_cards': 'Result scratch cards',
    'paystack': 'Secure online payment processing',
    'multi_campus': 'Multi-campus management',
    'custom_workflows': 'Custom workflows and approvals',
}

BASIC_FEATURES = [
    'core', 'attendance', 'results', 'fees', 'timetable'
]
PREMIUM_FEATURES = BASIC_FEATURES + [
    'notifications', 'cbt', 'analytics', 'bulk_import', 'promotion', 'scratch_cards', 'paystack'
]
ENTERPRISE_FEATURES = PREMIUM_FEATURES + ['multi_campus', 'custom_workflows']
PLAN_FEATURES = {
    'free': ['core'],
    'basic': BASIC_FEATURES,
    'premium': PREMIUM_FEATURES,
    'enterprise': ENTERPRISE_FEATURES,
}

BILLING_RATES = {
    'basic': {
        'standard': Decimal('800'),
        'discounted': Decimal('720'),
    },
    'premium': {
        'standard': Decimal('1500'),
        'discounted': Decimal('1350'),
    },
    'enterprise': {
        'standard': Decimal('2500'),
        'discounted': Decimal('2250'),
    },
}


def normalize_plan(plan_code):
    code = (plan_code or 'free').lower()
    return code if code in PLAN_FEATURES else 'free'


def resolve_plan(school=None, plan_code=None):
    if school is not None and getattr(school, 'subscription_plan', None):
        return normalize_plan(school.subscription_plan)
    return normalize_plan(plan_code)


def entitlements(school):
    plan = resolve_plan(school)
    return {'plan': plan, 'features': PLAN_FEATURES[plan], 'labels': FEATURES}


def has_feature(school, feature_name):
    if not feature_name:
        return False
    return feature_name in PLAN_FEATURES.get(resolve_plan(school), ['core'])


def calculate_billing_snapshot(*, school=None, session=None, term=None, plan_code='premium', active_student_count=0):
    """Return a billing snapshot for the selected plan and active-student count."""
    count = int(active_student_count or 0)
    plan_code = normalize_plan(plan_code)
    rate_table = BILLING_RATES.get(plan_code, BILLING_RATES['premium'])
    standard_rate = rate_table['standard']
    discounted_rate = rate_table['discounted']
    discount_percentage = 10 if count >= 100 else 0
    discount_eligible = count >= 100

    if discount_eligible:
        unit_price = discounted_rate
        base_amount = (Decimal(count) * standard_rate).quantize(Decimal('0.01'))
        discount_amount = (base_amount * Decimal(discount_percentage) / Decimal('100')).quantize(Decimal('0.01'))
        final_amount = (base_amount - discount_amount).quantize(Decimal('0.01'))
    else:
        unit_price = standard_rate
        base_amount = (Decimal(count) * unit_price).quantize(Decimal('0.01'))
        discount_amount = Decimal('0.00')
        final_amount = base_amount

    snapshot = {
        'school_id': getattr(school, 'pk', None),
        'session_id': getattr(session, 'pk', None),
        'term_id': getattr(term, 'pk', None),
        'plan_code': plan_code,
        'active_student_count': count,
        'standard_rate': float(standard_rate),
        'discount_eligible': discount_eligible,
        'discount_percentage': discount_percentage,
        'discount_amount': float(discount_amount),
        'effective_rate': float(unit_price),
        'unit_price': float(unit_price),
        'base_amount': float(base_amount),
        'subtotal': float(base_amount),
        'final_amount': float(final_amount),
        'currency': 'NGN',
    }
    snapshot['discount_amount'] = float(discount_amount)
    return snapshot


def required_plan_for_feature(feature_name):
    if feature_name in PLAN_FEATURES['enterprise'] and feature_name not in PLAN_FEATURES['premium']:
        return 'enterprise'
    if feature_name in PLAN_FEATURES['premium'] and feature_name not in PLAN_FEATURES['basic']:
        return 'premium'
    return 'basic' if feature_name in PLAN_FEATURES['basic'] else 'premium'


def required_feature(path):
    # Billing, callbacks and historical receipt retrieval remain reachable.
    if path == '/api/results/check/':
        return None
    if path.startswith(('/api/fees/subscription/', '/api/fees/pay/verify/', '/api/fees/receipts/')):
        return None
    if path.startswith('/api/parent/dashboard/'):
        return 'results'
    if path.startswith(('/api/students/bulk-import/', '/api/staff/bulk-import/')):
        return 'bulk_import'
    for prefix, feature in [('attendance', 'attendance'), ('results', 'results'), ('gradebook', 'results'),
            ('fees', 'fees'), ('timetable', 'timetable'), ('notifications', 'notifications'), ('cbt', 'cbt'),
            ('analytics', 'analytics'), ('reports', 'analytics'), ('promotion', 'promotion'), ('scratch-cards', 'scratch_cards')]:
        if path.startswith('/api/' + prefix + '/'):
            return feature
    return None


class SchoolPlanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import JsonResponse
        school = getattr(request, 'tenant', None)
        feature = required_feature(request.path_info)
        if feature and not school and request.method != 'OPTIONS':
            return JsonResponse({'detail': 'Select a school to use this feature.'}, status=404)
        if school and request.method != 'OPTIONS' and feature and not has_feature(school, feature):
            required_plan = required_plan_for_feature(feature)
            return JsonResponse({
                'code': 'plan_feature_required',
                'feature': feature,
                'detail': FEATURES[feature] + ' is not included in this school plan.',
                'required_plan': required_plan,
            }, status=403)
        return self.get_response(request)
