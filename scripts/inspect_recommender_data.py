from django.contrib.auth import get_user_model
from ai_recommender.models import CourseSkill, UserSkill, Skill
from courses.models import Course
from enrollments.models import Enrollment

User = get_user_model()
user = User.objects.filter(id=1).first()

print('=== Recommender data inspection ===')
print('user found:', bool(user), getattr(user, 'id', None))

print('\n-- Courses --')
print('total_courses =', Course.objects.count())
print("published_courses =", Course.objects.filter(status='published').count())
print('sample_published_ids =', list(Course.objects.filter(status="published").values_list("id", flat=True)[:10]))

print('\n-- CourseSkill --')
print('total_course_skill_rows =', CourseSkill.objects.count())
print('distinct_courses_with_skill =', CourseSkill.objects.values_list('course_id', flat=True).distinct().count())
cs_sample = CourseSkill.objects.select_related('skill', 'course')[:10]
for cs in cs_sample:
    print('CourseSkill -> course_id=', cs.course_id, 'skill_id=', cs.skill_id, 'weight=', cs.weight, 'skill_name=', getattr(cs.skill, 'name', None))

print('\n-- UserSkill (user id=1) --')
if user:
    us_qs = UserSkill.objects.filter(user=user)
    print('user_skill_count =', us_qs.count())
    for us in us_qs[:20]:
        print('UserSkill -> skill_id=', us.skill_id, 'proficiency=', us.proficiency)
else:
    print('no user with id=1')

print('\n-- Enrollments (user id=1) --')
if user:
    e_qs = Enrollment.objects.filter(user=user)
    print('enrollment_count =', e_qs.count())
    print('enrolled_course_ids =', list(e_qs.values_list('course_id', flat=True)[:20]))

print('\n=== End inspection ===')
