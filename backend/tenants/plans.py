"""One feature catalog for API enforcement and portal presentation."""
FEATURES = {
    'core': 'School setup, people and academic calendar',
    'attendance': 'Attendance tracking',
    'results': 'Scores and report cards',
    'fees': 'School fees and PDF receipts',
    'timetable': 'Timetable builder',
    'notifications': 'Email and SMS tools (provider usage charged separately)',
    'cbt': 'Computer-based exams and DOCX question import',
    'analytics': 'Advanced performance analytics',
    'bulk_import': 'Bulk student and staff imports',
    'promotion': 'Student promotion workflows',
    'scratch_cards': 'Result scratch cards',
}
PLAN_FEATURES = {
    'free': ['core'],
    'basic': ['core', 'attendance', 'results', 'fees', 'timetable', 'notifications'],
    'premium': list(FEATURES),
}

def entitlements(school):
    plan = school.subscription_plan if school.subscription_plan in PLAN_FEATURES else 'free'
    return {'plan': plan, 'features': PLAN_FEATURES[plan], 'labels': FEATURES}

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
        if school and request.method != 'OPTIONS' and feature and feature not in PLAN_FEATURES.get(school.subscription_plan, ['core']):
            return JsonResponse({'code': 'plan_feature_required', 'feature': feature,
                'detail': FEATURES[feature] + ' is not included in this school plan.',
                'required_plan': 'basic' if feature in PLAN_FEATURES['basic'] else 'premium'}, status=403)
        return self.get_response(request)
