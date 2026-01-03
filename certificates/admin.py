from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
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
        'certificate_id',
        'verification_code',
        'user__email',
        'user__username',
        'course__title',
    ]
    readonly_fields = [
        'id',
        'certificate_id',
        'verification_code',
        'verification_url_display',
        'issued_at',
        'last_downloaded_at',
        'download_count',
        'pdf_link',
    ]
    fieldsets = (
        ('Certificate Information', {
            'fields': (
                'id',
                'certificate_id',
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
                'pdf_file',
                'pdf_link',
                'download_count',
                'last_downloaded_at',
            )
        }),
    )
    date_hierarchy = 'issued_at'
    ordering = ['-issued_at']
    
    def certificate_id_display(self, obj):
        """Display truncated certificate ID."""
        return f"{str(obj.certificate_id)[:8]}..."
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
        if not obj.grade:
            return '-'
        
        color = 'green' if obj.grade >= 70 else 'orange' if obj.grade >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            obj.grade
        )
    grade_display.short_description = 'Grade'
    
    def pdf_status(self, obj):
        """Show PDF file status."""
        if obj.pdf_file:
            return format_html(
                '<span style="color: green;">✓ Generated</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Missing</span>'
        )
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
    
    def pdf_link(self, obj):
        """Display PDF download link."""
        if obj.pdf_file:
            return format_html(
                '<a href="{}" target="_blank">Download PDF</a>',
                obj.pdf_file.url
            )
        return '-'
    pdf_link.short_description = 'PDF File'
    
    def has_add_permission(self, request):
        """Certificates should only be created via API/services."""
        return False
