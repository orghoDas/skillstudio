from collections import defaultdict
from django.db import transaction
import logging

from django.conf import settings

from .models import Recommendation, CourseSkill, UserSkill, Skill
from courses.models import Course
from enrollments.models import Enrollment

logger = logging.getLogger(__name__)


def _load_user_skills(user):
    return {us.skill_id: us.proficiency for us in UserSkill.objects.filter(user=user)}


def _load_course_skills(course_qs):
    # returns dict: course_id -> list of (skill_id, weight)
    cs = CourseSkill.objects.filter(course__in=course_qs).select_related('skill')
    out = defaultdict(list)
    for c in cs:
        out[c.course_id].append((c.skill_id, c.weight))
    return out


def score_course_for_user(user, course, user_skill_map, course_skill_list):
    # Simple content-based score: sum(user_proficiency * course_skill_weight)
    score = 0.0
    matched = []
    for skill_id, weight in course_skill_list:
        prof = user_skill_map.get(skill_id)
        if prof is not None:
            score += float(prof) * float(weight)
            matched.append(skill_id)

    return score, matched


def generate_recommendations_for_user(user, top_n=10, exclude_enrolled=True, replace=True, min_score_threshold=10.0):
    """Compute and persist top-N recommendations for a user.

    - Gathers user's skill proficiencies from `UserSkill`.
    - Scores every course that has `CourseSkill` mappings.
    - Optionally excludes courses the user is already enrolled in.
    - Writes `Recommendation` records (simple replace behavior).
    """
    user_skill_map = _load_user_skills(user)
    logger.info("recommender.user_skills_loaded user_id=%s count=%d", getattr(user, 'id', user), len(user_skill_map))

    # candidate courses: those referenced by CourseSkill
    course_ids = CourseSkill.objects.values_list('course_id', flat=True).distinct()
    courses = Course.objects.filter(id__in=course_ids).select_related('current_version')
    logger.info("recommender.candidate_course_ids count=%d", course_ids.count())

    if exclude_enrolled:
        enrolled_course_ids = Enrollment.objects.filter(user=user).values_list('course_id', flat=True)
        courses = courses.exclude(id__in=list(enrolled_course_ids))
        logger.info("recommender.excluded_enrolled_count user_id=%s count=%d", getattr(user, 'id', user), len(list(enrolled_course_ids)))

    # Only consider published courses for recommendations
    courses = courses.filter(status='published')
    logger.info("recommender.candidate_courses_after_filters count=%d", courses.count())

    course_skill_map = _load_course_skills(courses)
    logger.info("recommender.course_skill_mappings_loaded entries=%d courses_with_skills=%d", sum(len(v) for v in course_skill_map.values()), len(course_skill_map))

    scored = []
    for course in courses:
        skills = course_skill_map.get(course.id, [])
        if not skills:
            continue
        raw_score, matched_skill_ids = score_course_for_user(user, course, user_skill_map, skills)
        if raw_score <= 0:
            continue

        # Normalize score to 0-100 by converting to weighted average of proficiencies
        total_weight = sum(w for _, w in skills) or 0
        if total_weight > 0:
            normalized = raw_score / total_weight
        else:
            normalized = 0

        final_score = max(0.0, min(100.0, round(float(normalized), 2)))
        if final_score < float(min_score_threshold):
            logger.debug("recommender.course_filtered_below_threshold course_id=%s score=%s threshold=%s", course.id, final_score, min_score_threshold)
            continue
        scored.append((final_score, course, matched_skill_ids))

    logger.info("recommender.scored_count=%d", len(scored))
    if scored:
        sample = scored[:min(5, len(scored))]
        for s, c, m in sample:
            logger.info("recommender.sample course_id=%s score=%s matched_skills=%s", c.id, s, m)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    with transaction.atomic():
        if replace:
            Recommendation.objects.filter(user=user, algorithm__startswith='mvp_').delete()

        to_create = []
        for score, course, matched in top:
            reason = f"Content-based match on {len(matched)} skill(s)"
            rec = Recommendation(
                user=user,
                course=course,
                score=score,
                algorithm='mvp_content_v1',
                reason=reason,
                status='active',
            )
            to_create.append((rec, matched))

        if not to_create:
            logger.info("recommender.no_recommendations user_id=%s", getattr(user, 'id', user))
            return []

        rec_instances = [r for r, _ in to_create]

        # Use return_defaults when available (Django >=4) to populate PKs; fallback to per-object save
        try:
            rec_objs = Recommendation.objects.bulk_create(rec_instances, return_defaults=True)
        except TypeError:
            # Older Django or DB backend fallback
            rec_objs = []
            for inst in rec_instances:
                inst.save()
                rec_objs.append(inst)

        # attach matched skills (ids list is acceptable)
        for (r, matched), obj in zip(to_create, rec_objs):
            if matched:
                try:
                    obj.matched_skills.set(matched)
                except Exception:
                    # best-effort: ignore if set fails for some reason
                    pass

        # emit simple metric via logging
        logger.info("recommender.created count=%d user_id=%s top_n=%d", len(rec_objs), getattr(user, 'id', user), top_n)

        return rec_objs
