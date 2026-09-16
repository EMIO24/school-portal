from accounts.school_access import assigned_classes
from accounts.school_access import SchoolModulePermission, require_assignment
"""Gradebook views."""
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from tenants.mixins import TenantMixin
from .models import GradeScale, ScoreEntry, AffectiveDomain, PsychomotorDomain
from .serializers import GradeScaleSerializer, ScoreEntryReadSerializer, ScoreEntryWriteSerializer, BulkScoreUpdateSerializer, AffectiveDomainSerializer, PsychomotorDomainSerializer, CA_MAXIMA, MAX_CA_TOTAL, MAX_EXAM

class ScoreEntryViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes=[SchoolModulePermission]; http_method_names=['get','post','patch','delete','head','options']
    def get_serializer_class(self): return ScoreEntryWriteSerializer if self.request.method in ('POST','PATCH') else ScoreEntryReadSerializer
    def get_queryset(self):
        qs=ScoreEntry.objects.filter(school=self.school).select_related('student','student__student_profile','subject','class_arm','term','session'); p=self.request.query_params
        if p.get('class_arm'): qs=qs.filter(class_arm_id=p['class_arm'])
        if p.get('subject'): qs=qs.filter(subject_id=p['subject'])
        if p.get('term'): qs=qs.filter(term_id=p['term'])
        if p.get('session'): qs=qs.filter(session_id=p['session'])
        if self.request.user.role=='teacher': qs=qs.filter(class_arm_id__in=assigned_classes(self.request))
        return qs
    @action(detail=False,url_path='grade-scale',methods=['get'])
    def grade_scale(self,request):
        bands=GradeScale.objects.filter(school=self.school).order_by('-min_score'); return Response({'bands':GradeScaleSerializer(bands,many=True).data,'ca_maxima':CA_MAXIMA,'max_ca':MAX_CA_TOTAL,'max_exam':MAX_EXAM})
    @action(detail=False,url_path='bulk-update',methods=['post'])
    @transaction.atomic
    def bulk_update(self,request):
        ser=BulkScoreUpdateSerializer(data=request.data); ser.is_valid(raise_exception=True); d=ser.validated_data
        require_assignment(request,d['class_arm'],d['term'],d['subject'])
        validated=[]
        for item in d['scores']:
            instance=ScoreEntry.objects.select_for_update().filter(school=self.school,student_id=item['student_id'],subject_id=d['subject'],term_id=d['term'],session_id=d['session'],class_arm_id=d['class_arm']).first()
            payload={k:v for k,v in item.items() if k!='student_id'}; payload.update(student=item['student_id'],subject=d['subject'],term=d['term'],session=d['session'],class_arm=d['class_arm'])
            row=ScoreEntryWriteSerializer(instance,data=payload,context=self.get_serializer_context()); row.is_valid(raise_exception=True); validated.append(row)
        ids=[row.save().pk for row in validated]; rows=ScoreEntry.objects.filter(id__in=ids).select_related('student','student__student_profile','subject','class_arm','term','session')
        return Response({'updated':ScoreEntryReadSerializer(rows,many=True).data,'errors':{}})
    @action(detail=False,url_path='publish',methods=['post'])
    def publish(self,request):
        p=request.query_params
        if not(p.get('class_arm') and p.get('subject') and p.get('term')): return Response({'detail':'class_arm, subject and term params required.'},status=status.HTTP_400_BAD_REQUEST)
        require_assignment(request,p['class_arm'],p['term'],p['subject'])
        count=ScoreEntry.objects.filter(school=self.school,class_arm_id=p['class_arm'],subject_id=p['subject'],term_id=p['term'],is_published=False).update(is_published=True)
        return Response({'published':count})
    @action(detail=False,methods=['post'],url_path='reopen')
    @transaction.atomic
    def reopen(self,request):
        from rest_framework.exceptions import ValidationError,PermissionDenied
        from tenants.models import PlatformEvent
        if request.user.role!='school_admin': raise PermissionDenied('Only school administrators can reopen results.')
        reason,ids=str(request.data.get('reason','')).strip(),request.data.get('entry_ids')
        if len(reason)<10: raise ValidationError('Explain the correction (at least 10 characters).')
        if not isinstance(ids,list) or not ids or len(ids)>1000: raise ValidationError('Select the entries to reopen.')
        rows=list(ScoreEntry.objects.select_for_update().filter(school=self.school,pk__in=ids))
        if len(rows)!=len(set(ids)): raise ValidationError('Select entries from this school.')
        PlatformEvent.objects.create(actor=request.user,actor_email=request.user.email,action='school.results_reopened',target=str(self.school.pk),details={'school_id':self.school.pk,'reason':reason[:2000],'entries':[{'id':r.pk,'total':str(r.total_score),'grade':r.grade} for r in rows]})
        ScoreEntry.objects.filter(pk__in=[r.pk for r in rows]).update(is_published=False); return Response({'reopened':len(rows)})

class AffectiveDomainViewSet(TenantMixin,viewsets.ModelViewSet):
    permission_classes=[SchoolModulePermission]; serializer_class=AffectiveDomainSerializer
    def get_queryset(self):
        qs=AffectiveDomain.objects.filter(school=self.school).select_related('student'); p=self.request.query_params
        if p.get('class_arm'): qs=qs.filter(class_arm_id=p['class_arm'])
        if p.get('term'): qs=qs.filter(term_id=p['term'])
        if self.request.user.role=='teacher': qs=qs.filter(class_arm_id__in=assigned_classes(self.request))
        return qs
    @action(detail=False,url_path=r'student/(?P<student_id>\d+)/term/(?P<term_id>\d+)',methods=['get','put'])
    def student_term(self,request,student_id=None,term_id=None):
        from django.contrib.auth import get_user_model
        User=get_user_model()
        if not User.objects.filter(pk=student_id,school=self.school,role='student').exists(): return Response({'detail':'Student not found.'},status=404)
        from academics.models import Term
        if not Term.objects.filter(pk=term_id,session__school=self.school).exists(): return Response({'detail':'Term not found.'},status=404)
        instance=AffectiveDomain.objects.filter(school=self.school,student_id=student_id,term_id=term_id).first()
        if request.method=='GET':
            if not instance:return Response({'detail':'No ratings recorded.'},status=404)
            require_assignment(request,instance.class_arm_id,term_id); return Response(AffectiveDomainSerializer(instance).data)
        ser=AffectiveDomainSerializer(instance,data={**request.data,'student':student_id,'term':term_id},partial=instance is not None,context=self.get_serializer_context()); ser.is_valid(raise_exception=True); instance=ser.save(); instance.refresh_from_db(); return Response(AffectiveDomainSerializer(instance).data)

class PsychomotorDomainViewSet(TenantMixin,viewsets.ModelViewSet):
    permission_classes=[SchoolModulePermission]; serializer_class=PsychomotorDomainSerializer
    def get_queryset(self):
        qs=PsychomotorDomain.objects.filter(school=self.school).select_related('student'); p=self.request.query_params
        if p.get('class_arm'):qs=qs.filter(class_arm_id=p['class_arm'])
        if p.get('term'):qs=qs.filter(term_id=p['term'])
        if self.request.user.role=='teacher':qs=qs.filter(class_arm_id__in=assigned_classes(self.request))
        return qs
    @action(detail=False,url_path=r'student/(?P<student_id>\d+)/term/(?P<term_id>\d+)',methods=['get','put'])
    def student_term(self,request,student_id=None,term_id=None):
        from django.contrib.auth import get_user_model
        User=get_user_model()
        if not User.objects.filter(pk=student_id,school=self.school,role='student').exists():return Response({'detail':'Student not found.'},status=404)
        from academics.models import Term
        if not Term.objects.filter(pk=term_id,session__school=self.school).exists():return Response({'detail':'Term not found.'},status=404)
        instance=PsychomotorDomain.objects.filter(school=self.school,student_id=student_id,term_id=term_id).first()
        if request.method=='GET':
            if not instance:return Response({'detail':'No ratings recorded.'},status=404)
            require_assignment(request,instance.class_arm_id,term_id);return Response(PsychomotorDomainSerializer(instance).data)
        ser=PsychomotorDomainSerializer(instance,data={**request.data,'student':student_id,'term':term_id},partial=instance is not None,context=self.get_serializer_context());ser.is_valid(raise_exception=True);instance=ser.save();instance.refresh_from_db();return Response(PsychomotorDomainSerializer(instance).data)
