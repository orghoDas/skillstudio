from datetime import timedelta
from math import ceil

from django.contrib.admin.models import LogEntry
from django.contrib.admin.sites import AdminSite
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.text import capfirst
from rest_framework.throttling import SimpleRateThrottle


class StaffLoginThrottle(SimpleRateThrottle):
    scope = 'staff_login'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class SkillStudioAdminSite(AdminSite):
    site_header = 'SkillStudio administration'
    site_title = 'SkillStudio Admin'
    index_title = 'Operations overview'
    index_template = 'administration/dashboard.html'

    def login(self, request, extra_context=None):
        if request.method == 'POST':
            throttle = StaffLoginThrottle()
            if not throttle.allow_request(request, self):
                return HttpResponse(
                    'Too many staff sign-in attempts. Try again shortly.',
                    status=429, headers={'Retry-After': str(ceil(throttle.wait() or 1))},
                    content_type='text/plain',
                )
        return super().login(request, extra_context)

    def _changelist(self, model, **filters):
        opts = model._meta
        return reverse(f'{self.name}:{opts.app_label}_{opts.model_name}_changelist', query=filters)

    def _record_url(self, request, obj):
        model_admin = self._registry[type(obj)]
        if hasattr(model_admin, 'workflow_url') and model_admin.can_run_workflow(request, obj):
            return model_admin.workflow_url(obj)
        opts = obj._meta
        return reverse(f'{self.name}:{opts.app_label}_{opts.model_name}_change', args=[obj.pk])

    def _activity(self, request):
        models = [
            model for model, model_admin in self._registry.items()
            if model_admin.has_view_or_change_permission(request)
        ]
        content_types = ContentType.objects.get_for_models(*models).values()
        entries = LogEntry.objects.filter(content_type__in=content_types).select_related('user')
        if not request.user.has_perm('admin.view_logentry'):
            entries = entries.filter(user=request.user)
        return [{
            'object': entry.object_repr,
            'message': entry.get_change_message(),
            'operator': entry.user.get_username(),
            'time': entry.action_time,
        } for entry in entries[:8]]

    def index(self, request, extra_context=None):
        from accounts.models import User
        from certificates.models import Certificate
        from courses.models import Course
        from enrollments.constants import ACCESS_STATUSES
        from enrollments.models import Enrollment
        from payments.models import Payment, Payout, Refund
        from payments.services import SETTLED_PAYMENT_STATUSES, with_payment_refunds

        def can_view(model):
            model_admin = self._registry.get(model)
            return model_admin and model_admin.has_view_or_change_permission(request)

        metrics = []
        queues = []
        trend = []

        def count(label, queryset, detail, **filters):
            metrics.append({
                'label': label, 'value': queryset.count(), 'detail': detail,
                'url': self._changelist(queryset.model, **filters),
            })

        def queue(title, queryset, date_field, description, label=str, **filters):
            model = queryset.model
            queues.append({
                'title': title,
                'description': description,
                'url': self._changelist(model, **filters),
                'items': [{
                    'label': label(obj),
                    'date': getattr(obj, date_field) or obj.created_at,
                    'url': self._record_url(request, obj),
                    'status': capfirst(obj.get_status_display()) if hasattr(obj, 'get_status_display') else '',
                } for obj in queryset.order_by(Coalesce(date_field, 'created_at'), 'pk')[:5]],
            })

        if can_view(User):
            count('Active accounts', User.objects.filter(is_active=True), 'Students, instructors and staff', is_active__exact=1)
        if can_view(Course):
            count('Published courses', Course.objects.filter(status='published'), 'Visible in the catalogue', status__exact='published')
            review = Course.objects.filter(status='under_review').select_related('instructor', 'category')
            count('Courses in review', review, 'Awaiting a publishing decision', status__exact='under_review')
            queue('Course review', review, 'submitted_for_review_at', 'Submissions awaiting a publishing decision.',
                  status__exact='under_review')
        if can_view(Enrollment):
            count('Learning enrollments', Enrollment.objects.filter(status__in=ACCESS_STATUSES), 'Active and completed',
                  status__in=','.join(ACCESS_STATUSES))
            today = timezone.localdate()
            start = today - timedelta(days=13)
            counts = dict(
                Enrollment.objects.filter(enrolled_at__date__gte=start, enrolled_at__date__lte=today)
                .annotate(day=TruncDate('enrolled_at')).values('day').annotate(total=Count('pk'))
                .values_list('day', 'total')
            )
            peak = max(counts.values(), default=1)
            trend = [{
                'day': day, 'count': counts.get(day, 0),
                'height': round(counts.get(day, 0) * 100 / peak),
            } for day in (start + timedelta(days=offset) for offset in range(14))]
        if can_view(Certificate):
            count('Valid certificates', Certificate.objects.filter(revoked_at__isnull=True), 'Issued and currently valid',
                  revoked_at__isnull='True')
        if can_view(Payment):
            sales = with_payment_refunds(Payment.objects.filter(
                purpose=Payment.PURPOSE_COURSE_PURCHASE,
                status__in=SETTLED_PAYMENT_STATUSES,
            )).order_by().values('currency').annotate(total=Sum('net_amount')).order_by('currency')
            metrics.append({
                'label': 'Net course sales',
                'amounts': list(sales) or [{'total': 0, 'currency': 'USD'}],
                'detail': 'All-time course sales after refunds',
                'url': self._changelist(Payment),
            })
        if can_view(Refund):
            refunds = Refund.objects.filter(status='requested').select_related('payment', 'requested_by')
            count('Refund requests', refunds, 'Awaiting a wallet refund decision', status__exact='requested')
            queue(
                'Wallet refunds', refunds, 'requested_at', 'Refund requests for course purchases.',
                label=lambda refund: f'Refund #{refund.pk} · {refund.payment.currency} {refund.amount}',
                status__exact='requested',
            )
        if can_view(Payout):
            payouts = Payout.objects.filter(status__in=('pending', 'processing')).select_related('instructor')
            count('Open payouts', payouts, 'Pending or processing', status__in='pending,processing')
            queue(
                'Manual payouts', payouts, 'created_at', 'Payouts awaiting approval or transfer confirmation.',
                label=lambda payout: f'Payout #{payout.pk} · {payout.currency} {payout.amount} · {payout.instructor.email}',
                status__in='pending,processing',
            )

        context = {'metrics': metrics, 'queues': queues, 'trend': trend, 'activity': self._activity(request)}
        context.update(extra_context or {})
        return super().index(request, extra_context=context)
