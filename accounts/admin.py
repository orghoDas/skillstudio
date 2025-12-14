from django.contrib import admin
from .models import User, Profile, EmailVerificationToken, PasswordResetToken

admin.site.register(Profile)
admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'role', 'is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'username')
    list_filter = ('role', 'is_active', 'is_staff')
    ordering = ('email',)