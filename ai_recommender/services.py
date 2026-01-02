from accounts import models
from .models import UserSkill
from courses.models import Course, CourseSkill
from enrollments.models import Enrollment
from reviews.models import Review
from django.utils.timezone import now
from datetime import timedelta


def update_user_skills(user):
    enrollments = Enrollment.objects.filter(user=user, is_completed=True)

    for enrollment in enrollments:
        for cs in CourseSkill.objects.filter(course=enrollment.course):
            obj, _ = UserSkill.objects.get_or_create(
                user=user,
                skill=cs.skill
            )
            obj.proficiency += cs.weight
            obj.save(update_fields=["proficiency"])



def get_skill_gaps(user, target_skills):
    user_skills = {
        us.skill_id: us.proficiency
        for us in UserSkill.objects.filter(user=user)
    }

    gaps = []
    for skill in target_skills:
        proficiency = user_skills.get(skill.id, 0)
        if proficiency < 1:
            gaps.append(skill)

    return gaps


def course_quality_score(course):
    enrollments = Enrollment.objects.filter(course=course).count()
    completions = Enrollment.objects.filter(
        course=course, is_completed=True
    ).count()

    completion_rate = completions / max(enrollments, 1)

    rating = Review.objects.filter(course=course).aggregate(avg=models.Avg("rating"))["avg"] or 0

    return (completion_rate * 0.6) + ((rating / 5) * 0.4)


def similar_users(user):
    user_courses = set(
        Enrollment.objects.filter(user=user)
        .values_list("course_id", flat=True)
    )

    similarities = []

    for other in Enrollment.objects.exclude(user=user).values("user").distinct():
        other_courses = set(
            Enrollment.objects.filter(user=other["user"])
            .values_list("course_id", flat=True)
        )

        overlap = len(user_courses & other_courses)
        if overlap:
            similarities.append((other["user"], overlap))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return [u for u, _ in similarities[:10]]


def recommend_courses(user, limit=10):
    completed = Enrollment.objects.filter(
        user=user, is_completed=True
    ).values_list("course_id", flat=True)

    scores = {}

    # Skill-based
    for cs in CourseSkill.objects.all():
        if cs.course_id in completed:
            continue
        scores.setdefault(cs.course_id, 0)
        scores[cs.course_id] += cs.weight

    # Collaborative
    for u in similar_users(user):
        for e in Enrollment.objects.filter(user=u):
            scores.setdefault(e.course_id, 0)
            scores[e.course_id] += 1.5

    # Quality filter
    final = []
    for cid, score in scores.items():
        course = Course.objects.get(id=cid)
        quality = course_quality_score(course)
        if quality >= 0.4:
            final.append((course, score * quality))

    final.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in final[:limit]]


def trending_skills(days=30):
    recent = Enrollment.objects.filter(
        enrolled_at__gte=now() - timedelta(days=days)
    )

    skills = {}
    for e in recent:
        for cs in CourseSkill.objects.filter(course=e.course):
            skills[cs.skill.name] = skills.get(cs.skill.name, 0) + 1

    return sorted(skills.items(), key=lambda x: x[1], reverse=True)