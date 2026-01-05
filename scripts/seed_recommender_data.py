from django.contrib.auth import get_user_model
from ai_recommender.models import Skill, CourseSkill, UserSkill
from courses.models import Course

User = get_user_model()

user = User.objects.filter(id=1).first()
if not user:
    print('No user with id=1 found; aborting')
else:
    print('Seeding recommender test data for user id=1')

    # Create sample skills
    skill_names = ['Python', 'Django', 'Data Analysis', 'Machine Learning']
    skills = []
    for name in skill_names:
        slug = name.lower().replace(' ', '-')
        skill, created = Skill.objects.get_or_create(name=name, defaults={'slug': slug, 'category': 'technical'})
        skills.append(skill)
        print('Skill:', skill.id, skill.name, 'created=', created)

    # Pick some published courses to attach skills to (limit 5)
    published_courses = list(Course.objects.filter(status='published')[:5])
    if not published_courses:
        print('No published courses found; aborting')
    else:
        for idx, course in enumerate(published_courses):
            # attach 1-2 skills per course with varying weights
            sk = skills[idx % len(skills)]
            sk2 = skills[(idx + 1) % len(skills)]
            cs1, c1_created = CourseSkill.objects.get_or_create(course=course, skill=sk, defaults={'weight': 1.0, 'is_primary': True})
            cs2, c2_created = CourseSkill.objects.get_or_create(course=course, skill=sk2, defaults={'weight': 0.6, 'is_primary': False})
            print('CourseSkill:', course.id, getattr(course, 'title', None), '->', sk.name, 'created=', c1_created)
            print('CourseSkill:', course.id, getattr(course, 'title', None), '->', sk2.name, 'created=', c2_created)

        # Add user skills for user
        # Give user moderate proficiency in first two skills
        for i, skill in enumerate(skills[:2]):
            us, created = UserSkill.objects.get_or_create(user=user, skill=skill, defaults={'proficiency': 60.0 if i == 0 else 45.0})
            if not created:
                us.proficiency = 60.0 if i == 0 else 45.0
                us.save(update_fields=['proficiency'])
            print('UserSkill:', user.id, skill.name, 'proficiency=', us.proficiency)

    print('Seeding complete')
