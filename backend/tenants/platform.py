"""Owner-only school administration; public signup always creates pending schools."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from accounts.permissions import IsSuperAdmin, IsPlatformReader
from .security import audit
from .models import School, SchoolActivity
from .serializers import SchoolSerializer

User = get_user_model()


class AdministratorInput(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email already has an account. Use a different email.")
        return value

    def validate(self, attrs):
        try:
            validate_password(attrs['password'], User(**{k: v for k, v in attrs.items() if k != 'password'}))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs


class RegistrationInput(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    subdomain = serializers.RegexField(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=63)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    administrator = AdministratorInput(write_only=True)

    def validate_subdomain(self, value):
        if value in {'www', 'api', 'admin', 'superadmin', 'platform', 'mail', 'support', 'localhost'}:
            raise serializers.ValidationError("Please choose another school identifier.")
        if School.objects.filter(Q(subdomain__iexact=value) | Q(slug__iexact=value)).exists():
            raise serializers.ValidationError("That school identifier is already in use.")
        return value


class SchoolUpdate(serializers.ModelSerializer):
    def validate_theme_config(self, value):
        from .branding import validate_theme
        return validate_theme(value)

    class Meta:
        model = School
        fields = ['name', 'email', 'phone', 'address', 'logo', 'motto', 'subscription_plan',
                  'subscription_ends_on', 'platform_notes', 'theme_config']


def school_queryset():
    return School.objects.annotate(
        user_count=Count('users', distinct=True),
        student_count=Count('users', filter=Q(users__role='student'), distinct=True),
        teacher_count=Count('users', filter=Q(users__role='teacher'), distinct=True),
        admin_count=Count('users', filter=Q(users__role='school_admin'), distinct=True),
    )


def school_data(school, detail=False):
    data = SchoolSerializer(school).data
    from .plans import entitlements
    data["entitlements"] = entitlements(school)
    data.update(approval_status=school.approval_status,
                subscription_ends_on=school.subscription_ends_on,
                platform_notes=school.platform_notes,
                usage={key: getattr(school, key, 0) for key in
                       ['user_count', 'student_count', 'teacher_count', 'admin_count']})
    if detail:
        data['administrators'] = list(school.users.filter(role='school_admin').values(
            'id', 'email', 'first_name', 'last_name', 'is_active', 'last_login'))
        data['activity'] = list(school.platform_activity.values('action', 'created_at', 'actor__email')[:30])
    return data


def create_school(data, actor=None):
    admin = data.pop('administrator')
    try:
        with transaction.atomic():
            school = School.objects.create(**data, slug=data['subdomain'],
                is_active=actor is not None, approval_status='approved' if actor else 'pending')
            User.objects.create_user(**admin, role='school_admin', school=school,
                                     must_change_password=actor is not None)
            SchoolActivity.objects.create(school=school, actor=actor,
                action='School created by owner' if actor else 'School registration submitted')
    except IntegrityError:
        raise serializers.ValidationError('School identifier or administrator email is already in use.')
    return school


class SignupThrottle(AnonRateThrottle):
    rate = '5/hour'


class SchoolRegistration(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [SignupThrottle]

    def post(self, request):
        serializer = RegistrationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = create_school(dict(serializer.validated_data))
        audit(request, 'school.registration', school.pk, {'name': school.name})
        return Response({'detail': 'Registration submitted. Your school must be approved before you can sign in.',
                         'subdomain': school.subdomain, 'approval_status': 'pending'}, status=201)


class PlatformSchools(APIView):
    permission_classes = [IsPlatformReader]

    def get(self, request):
        qs = school_queryset()
        summary = {'schools': qs.count(), 'active': qs.filter(is_active=True).count(),
                   'pending': qs.filter(approval_status='pending').count(),
                   'users': User.objects.filter(school__isnull=False).count()}
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(subdomain__icontains=search) | Q(email__icontains=search))
        state = request.query_params.get('status')
        if state in ['pending', 'rejected']:
            qs = qs.filter(approval_status=state)
        elif state == 'active':
            qs = qs.filter(approval_status='approved', is_active=True)
        elif state == 'suspended':
            qs = qs.filter(approval_status='approved', is_active=False)
        if request.query_params.get('plan') in dict(School.SUBSCRIPTION_CHOICES):
            qs = qs.filter(subscription_plan=request.query_params['plan'])
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            raise serializers.ValidationError({'page': 'Enter a page number.'})
        return Response({'summary': summary, 'count': qs.count(), 'results':
                         [school_data(s) for s in qs.order_by('-created_at', '-id')[(page-1)*20:page*20]]})

    def post(self, request):
        serializer = RegistrationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = create_school(dict(serializer.validated_data), request.user)
        audit(request, 'school.created', school.pk, {'name': school.name, 'administrator': school.users.get(role='school_admin').email})
        return Response(school_data(school_queryset().get(pk=school.pk), True), status=201)


class PlatformSchoolDetail(APIView):
    permission_classes = [IsPlatformReader]

    def get(self, request, pk):
        return Response(school_data(get_object_or_404(school_queryset(), pk=pk), True))

    @transaction.atomic
    def patch(self, request, pk):
        school = get_object_or_404(School.objects.select_for_update(), pk=pk)
        serializer = SchoolUpdate(school, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        before = {key: str(getattr(school, key)) for key in serializer.validated_data}
        serializer.save()
        audit(request, "school.updated", school.pk, {key: {"before": before[key], "after": str(getattr(school, key))} for key in before})
        SchoolActivity.objects.create(school=school, actor=request.user, action='School details or subscription updated')
        return Response(school_data(school_queryset().get(pk=pk), True))

    @transaction.atomic
    def post(self, request, pk):
        school = get_object_or_404(School.objects.select_for_update(), pk=pk)
        action = request.data.get('action')
        if action in ['approve', 'reject']:
            if school.approval_status != 'pending':
                raise serializers.ValidationError('Only pending registrations can be approved or rejected.')
            school.approval_status = 'approved' if action == 'approve' else 'rejected'
            school.is_active = action == 'approve'
        elif action in ['suspend', 'activate']:
            if school.approval_status != 'approved':
                raise serializers.ValidationError('Approve the registration before changing access.')
            school.is_active = action == 'activate'
        else:
            raise serializers.ValidationError({'action': 'Choose approve, reject, suspend or activate.'})
        school.save(update_fields=['approval_status', 'is_active'])
        audit(request, 'school.' + action, school.pk, {'approval_status': school.approval_status, 'is_active': school.is_active})
        SchoolActivity.objects.create(school=school, actor=request.user, action='School: ' + action)
        return Response(school_data(school_queryset().get(pk=pk), True))


class PlatformAdministrators(APIView):
    permission_classes = [IsSuperAdmin]

    @transaction.atomic
    def post(self, request, pk):
        school = get_object_or_404(School, pk=pk)
        serializer = AdministratorInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = User.objects.create_user(**serializer.validated_data, school=school,
                    role='school_admin', must_change_password=True)
        except IntegrityError:
            raise serializers.ValidationError({'email': 'This email already has an account.'})
        audit(request, 'school.administrator_added', school.pk, {'email': user.email})
        SchoolActivity.objects.create(school=school, actor=request.user, action='Administrator added: ' + user.email)
        return Response(school_data(school_queryset().get(pk=pk), True), status=201)

    @transaction.atomic
    def patch(self, request, pk):
        school = get_object_or_404(School.objects.select_for_update(), pk=pk)
        try:
            user_id = int(request.data.get('id'))
        except (ValueError, TypeError):
            raise serializers.ValidationError({'id': 'Choose an administrator.'})
        user = get_object_or_404(User, pk=user_id, school=school, role='school_admin')
        active = request.data.get('is_active')
        if not isinstance(active, bool):
            raise serializers.ValidationError({'is_active': 'Choose true or false.'})
        if not active and user.is_active and school.users.filter(role='school_admin', is_active=True).count() <= 1:
            raise serializers.ValidationError('Add another active administrator before disabling the last one.')
        user.is_active = active
        user.save(update_fields=['is_active'])
        audit(request, 'school.administrator_access', school.pk, {'email': user.email, 'is_active': active})
        SchoolActivity.objects.create(school=school, actor=request.user,
            action=('Administrator activated: ' if active else 'Administrator disabled: ') + user.email)
        return Response(school_data(school_queryset().get(pk=pk), True))


class PlatformProfile(APIView):
    permission_classes = [IsPlatformReader]

    def get(self, request):
        from accounts.serializers import UserProfileSerializer
        return Response(UserProfileSerializer(request.user).data)


class PlatformAccounts(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from .models import PlatformSecurity
        rows = []
        for user in User.objects.filter(role='superadmin').select_related('platform_security'):
            state = getattr(user, 'platform_security', None)
            rows.append({'id': user.pk, 'email': user.email, 'first_name': user.first_name,
                'last_name': user.last_name, 'is_active': user.is_active,
                'access_level': state.access_level if state else 'owner', 'mfa_enabled': bool(state and state.enabled)})
        return Response(rows)

    @transaction.atomic
    def post(self, request):
        from .models import PlatformSecurity
        serializer = AdministratorInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        access = request.data.get('access_level', 'viewer')
        if access not in ('owner', 'viewer'):
            raise serializers.ValidationError({'access_level': 'Choose owner or viewer.'})
        try:
            with transaction.atomic():
                user = User.objects.create_user(**serializer.validated_data, role='superadmin', school=None,
                    is_staff=False, is_superuser=False, must_change_password=True)
                PlatformSecurity.objects.create(user=user, access_level=access)
        except IntegrityError:
            raise serializers.ValidationError({'email': 'Email already in use.'})
        audit(request, 'platform.account_created', user.pk, {'email': user.email, 'access_level': access})
        return Response({'detail': 'Account created. Share the temporary password securely. Two-factor setup is required.'}, status=201)

    @transaction.atomic
    def patch(self, request):
        from .models import PlatformSecurity
        try:
            pk = int(request.data.get('id'))
        except (ValueError, TypeError):
            raise serializers.ValidationError({'id': 'Choose a platform account.'})
        user = get_object_or_404(User.objects.select_for_update(), pk=pk, role='superadmin')
        if user.pk == request.user.pk:
            raise serializers.ValidationError('You cannot disable your own account.')
        active = request.data.get('is_active')
        if not isinstance(active, bool):
            raise serializers.ValidationError({'is_active': 'Choose true or false.'})
        user.is_active = active
        user.save(update_fields=['is_active'])
        state, _ = PlatformSecurity.objects.get_or_create(user=user)
        state.session_version += 1
        state.challenge_nonce = ''
        state.save(update_fields=['session_version', 'challenge_nonce'])
        audit(request, 'platform.account_access', user.pk, {'email': user.email, 'is_active': active})
        return Response({'detail': 'Account access updated. Previous sessions revoked.'})


class PlatformAudit(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from .models import PlatformEvent
        qs = PlatformEvent.objects.all()
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(actor_email__icontains=search) | Q(action__icontains=search) | Q(target__icontains=search))
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            raise serializers.ValidationError({'page': 'Enter a page number.'})
        return Response({'count': qs.count(), 'results': list(qs.values(
            'id', 'actor_email', 'action', 'target', 'details', 'ip_address', 'created_at')[(page-1)*30:page*30])})


from accounts.permissions import IsPlatformMember

class PlatformPassword(APIView):
    permission_classes = [IsPlatformMember]

    def post(self, request):
        from accounts.serializers import ChangePasswordSerializer
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit(request, 'platform.password_changed', request.user.pk)
        return Response({'detail': 'Password updated.'})


class PlatformAppearance(APIView):
    permission_classes = [IsSuperAdmin]
    def get(self, request):
        from .plans import PLAN_FEATURES, FEATURES
        return Response({'schools': list(School.objects.order_by('name').values('id', 'name', 'subdomain')),
                         'plans': PLAN_FEATURES, 'features': FEATURES})
