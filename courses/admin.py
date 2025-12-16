from django.contrib import admin
from .models import (
    Course,
    Category,
    Tag,
    Module,
    Lesson,
    CourseVersion,
    CourseTag,
    LessonResource
)

class LessonResourceInline(admin.TabularInline):
    model = LessonResource
    extra = 1

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    show_change_link = True

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'category', 'status', 'is_free', 'price', 'level', 'created_at')
    list_filter = ('status', 'is_free', 'level', 'category')
    search_fields = ('title', 'instructor__username', 'category__name')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'position', 'created_at')
    list_filter = ('course',)
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'content_type', 'position', 'created_at')
    list_filter = ('content_type', 'module__course')
    search_fields = ('title', 'module__title', 'module__course__title')
    inlines = [LessonResourceInline]


admin.site.register(Category)
admin.site.register(Tag)
admin.site.register(CourseVersion)
admin.site.register(CourseTag)
admin.site.register(LessonResource)
