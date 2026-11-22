from django import forms
from django.contrib import admin
from django.contrib.admin.utils import quote, unquote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.http import require_http_methods
from rest_framework_simplejwt.token_blacklist.admin import (
    BlacklistedTokenAdmin as BaseBlacklistedTokenAdmin,
    OutstandingTokenAdmin as BaseOutstandingTokenAdmin,
)
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.utils import is_platform_admin


class ReadOnlyAdmin(admin.ModelAdmin):
    """Display records that are written through domain services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.unregister(OutstandingToken)
admin.site.unregister(BlacklistedToken)


@admin.register(OutstandingToken)
class OutstandingTokenAdmin(ReadOnlyAdmin, BaseOutstandingTokenAdmin):
    exclude = ('token',)

    def get_readonly_fields(self, request, obj=None):
        return [name for name in super().get_readonly_fields(request, obj) if name != 'token']


@admin.register(BlacklistedToken)
class BlacklistedTokenAdmin(BaseBlacklistedTokenAdmin):
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DecisionForm(forms.Form):
    action = forms.ChoiceField(label='Decision')
    note = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, choices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['action'].choices = [('', 'Select a decision'), *choices]


class WorkflowAdmin(ReadOnlyAdmin):
    """Keep model inspection read-only and route permitted decisions through services."""

    decision_form = DecisionForm
    change_form_template = 'administration/record.html'
    decision_help = ''

    def workflow_choices(self, obj):
        raise NotImplementedError

    def apply_decision(self, request, obj, data):
        raise NotImplementedError

    def decision_details(self, obj):
        return [('Status', obj.get_status_display())]

    def can_run_workflow(self, request, obj):
        opts = self.model._meta
        return (
            self.has_view_or_change_permission(request, obj)
            and is_platform_admin(request.user)
            and request.user.has_perm(f'{opts.app_label}.change_{opts.model_name}')
            and bool(self.workflow_choices(obj))
        )

    def _url_name(self, suffix):
        opts = self.model._meta
        return f'{opts.app_label}_{opts.model_name}_{suffix}'

    def get_urls(self):
        custom = [
            path('<path:object_id>/decision/', self.admin_site.admin_view(self.workflow_view),
                 name=self._url_name('decision')),
        ]
        return custom + super().get_urls()

    def workflow_url(self, obj):
        return reverse(f'{self.admin_site.name}:{self._url_name("decision")}', args=[quote(obj.pk)])

    def get_list_display(self, request):
        columns = super().get_list_display(request)

        @admin.display(description='Workflow')
        def decision(obj):
            if self.can_run_workflow(request, obj):
                return format_html('<a href="{}">Review</a>', self.workflow_url(obj))
            return '—'

        return (*columns, decision)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj is not None and self.can_run_workflow(request, obj):
            context['decision_url'] = self.workflow_url(obj)
        return super().render_change_form(request, context, add, change, form_url, obj)

    @method_decorator(require_http_methods(['GET', 'POST']))
    def workflow_view(self, request, object_id):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            raise Http404
        if not self.can_run_workflow(request, obj):
            raise PermissionDenied

        opts = self.model._meta
        list_url = reverse(f'{self.admin_site.name}:{self._url_name("changelist")}')
        detail_url = reverse(f'{self.admin_site.name}:{self._url_name("change")}', args=[quote(obj.pk)])
        form = self.decision_form(request.POST if request.method == 'POST' else None, choices=self.workflow_choices(obj))
        if form.is_valid():
            try:
                with transaction.atomic():
                    message = self.apply_decision(request, obj, form.cleaned_data)
                    obj.refresh_from_db()
                    self.log_change(request, obj, message)
            except ValidationError as error:
                for detail in error.messages:
                    form.add_error(None, detail)
            else:
                self.message_user(request, message)
                return redirect(detail_url)

        return TemplateResponse(request, 'administration/decision.html', {
            **self.admin_site.each_context(request),
            'title': f'Review {opts.verbose_name}',
            'opts': opts, 'record': obj, 'form': form,
            'list_url': list_url, 'detail_url': detail_url,
            'help_text': self.decision_help, 'details': self.decision_details(obj),
        })
