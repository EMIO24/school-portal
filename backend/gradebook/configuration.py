from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsSchoolAdmin
from academics.models import Term
from tenants.models import School, PlatformEvent
from .models import ScoreEntry, TermScoring
from .scoring import defaults, ScoringInput, json_values


class ScoringConfiguration(APIView):
    permission_classes = [IsSchoolAdmin]

    def term(self, request):
        term_id = serializers.IntegerField(min_value=1).run_validation(request.query_params.get('term'))
        return get_object_or_404(Term,pk=term_id,session__school=request.tenant)

    def get(self,request):
        term = self.term(request)
        policy = TermScoring.objects.filter(school=request.tenant,term=term).first()
        values = {'components':policy.components,'bands':policy.bands} if policy else defaults(request.tenant)
        return Response({**values,'configured':bool(policy),'locked':ScoreEntry.objects.filter(school=request.tenant,term=term).exists()})

    @transaction.atomic
    def put(self,request):
        school = School.objects.select_for_update().get(pk=request.tenant.pk)
        term = self.term(request)
        if ScoreEntry.objects.filter(school=school,term=term).exists():
            raise serializers.ValidationError('This term already has scores. Configure a future term instead.')
        form = ScoringInput(data=request.data);form.is_valid(raise_exception=True)
        policy = TermScoring.objects.filter(school=school,term=term).first() or TermScoring(school=school,term=term)
        for key,value in json_values(form.validated_data).items(): setattr(policy,key,value)
        policy.save()
        PlatformEvent.objects.create(actor=request.user,actor_email=request.user.email,action='school.scoring_configured',
            target=str(term.pk),details={'school_id':school.pk,'components':policy.components,'bands':policy.bands})
        return self.get(request)
