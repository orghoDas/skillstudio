from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from core.admin import ReadOnlyAdmin
from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(ReadOnlyAdmin):
    list_display = [
        'certificate_id_display',
        'user_link',
        'course_link',
        'grade_display',
        'issued_at',
        'download_count',
        'pdf_status',
    ]
    list_filter = [
        'issued_at',
        'completion_date',
        'last_downloaded_at',
    ]
    search_fields = [
        'id',
        'verification_code',
        'user__email',
        'user__username',
        'course__title',
    ]
    readonly_fields = [
        'id',
        'verification_code',
        'verification_url_display',
        'revoked_at',
        'issued_at',
        'last_downloaded_at',
        'download_count',
        'pdf_status',
    ]
    fieldsets = (
        ('Certificate Information', {
            'fields': (
                'id',
                'verification_code',
                'verification_url_display',
            )
        }),
        ('User & Course', {
            'fields': (
                'user',
                'course',
                'enrollment',
            )
        }),
        ('Performance', {
            'fields': (
                'grade',
                'completion_date',
            )
        }),
        ('Issuance & Downloads', {
            'fields': (
                'issued_at',
                'revoked_at',
                'pdf_status',
                'download_count',
                'last_downloaded_at',
            )
        }),
    )
    date_hierarchy = 'issued_at'
    ordering = ['-issued_at']
    
    def certificate_id_display(self, obj):
        """Display truncated certificate ID."""
        return f"{str(obj.pk)[:8]}..."
    certificate_id_display.short_description = 'Certificate ID'
    
    def user_link(self, obj):
        """Link to user admin."""
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    
    def course_link(self, obj):
        """Link to course admin."""
        url = reverse('admin:courses_course_change', args=[obj.course.id])
        return format_html('<a href="{}">{}</a>', url, obj.course.title)
    course_link.short_description = 'Course'
    
    def grade_display(self, obj):
        """Display grade with color coding."""
        if obj.grade is None:
            return '-'
        
        color = 'green' if obj.grade >= 70 else 'orange' if obj.grade >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{}%</span>',
            color,
            f'{obj.grade:.1f}',
        )
    grade_display.short_description = 'Grade'
    
    def pdf_status(self, obj):
        """Show PDF file status."""
        if obj.is_revoked:
            return 'Revoked'
        return 'Generated' if obj.pdf and obj.pdf_verification_url == obj.verification_url else 'On demand'
    pdf_status.short_description = 'PDF'
    
    def verification_url_display(self, obj):
        """Display clickable verification URL."""
        url = obj.verification_url
        return format_html(
            '<a href="{}" target="_blank">{}</a>',
            url,
            url
        )
    verification_url_display.short_description = 'Verification URL'
