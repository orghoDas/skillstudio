from django.contrib import admin
from .models import User, Profile, EmailVerificationToken, PasswordResetToken

admin.site.register(User)
admin.site.register(Profile)
admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)