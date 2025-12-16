from django.contrib import admin
from .models import Enrollment, LessonProgress, Wishlist

# Register your models here.

admin.site.register(Enrollment)
admin.site.register(LessonProgress)
admin.site.register(Wishlist)