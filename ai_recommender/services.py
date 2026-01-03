"""
AI Recommender Services
=======================
Comprehensive recommendation engine with multiple algorithms:
- Collaborative filtering
- Content-based filtering
- Skill gap analysis
- Trending courses
- Learning path recommendations
"""

from django.db import models as django_models, transaction
from django.utils import timezone
from django.db.models import Count, Avg, Q, F, Sum, Max
from datetime import timedelta
from decimal import Decimal
import logging

from .models import (
    Skill, CourseSkill, UserSkill, UserInterest,
    Recommendation, SkillGapAnalysis, TrendingSkill,
    LearningPath, PathCourse, UserLearningPath
)
from courses.models import Course
from enrollments.models import Enrollment
from social.models import Review

logger = logging.getLogger(__name__)


# ===========================
# Skill Management
# ===========================

def create_skill(name, category, description='', slug=None):
    """Create a new skill"""
    if not slug:
        from django.utils.text import slugify
        slug = slugify(name)
    
    skill, created = Skill.objects.get_or_create(
        name=name,
        defaults={
            'slug': slug,
            'category': category,
            'description': description,
        }
    )
    
    if not created and description:
        skill.description = description
        skill.save(update_fields=['description'])
    
    return skill


def add_skill_to_course(course, skill_name, weight=1.0, is_primary=False, added_by='instructor'):
    """Link a skill to a course"""
    skill = create_skill(skill_name, category='technical')  # Auto-create if needed
    
    course_skill, created = CourseSkill.objects.get_or_create(
        course=course,
        skill=skill,
        defaults={
            'weight': weight,
            'is_primary': is_primary,
            'added_by': added_by,
        }
    )
    
    if not created:
        course_skill.weight = weight
        course_skill.is_primary = is_primary
        course_skill.save(update_fields=['weight', 'is_primary'])
    
    return course_skill


def update_user_skills(user):
    """
    Update user's skill proficiency based on completed courses
    Called after course completion
    """
    completed_enrollments = Enrollment.objects.filter(
        user=user,
        is_completed=True
    ).select_related('course')
    
    skill_progress = {}
    
    for enrollment in completed_enrollments:
        # Get all skills taught in this course
        course_skills = CourseSkill.objects.filter(course=enrollment.course)
        
        for cs in course_skills:
            if cs.skill_id not in skill_progress:
                skill_progress[cs.skill_id] = {
                    'skill': cs.skill,
                    'proficiency': 0.0,
                    'sources': []
                }
            
            # Add weighted proficiency (primary skills contribute more)
            proficiency_gain = cs.weight * (15 if cs.is_primary else 10)
            skill_progress[cs.skill_id]['proficiency'] += proficiency_gain
            skill_progress[cs.skill_id]['sources'].append(enrollment.course.title)
    
    # Update or create UserSkill records
    updated_skills = []
    for skill_id, data in skill_progress.items():
        user_skill, created = UserSkill.objects.get_or_create(
            user=user,
            skill=data['skill'],
            defaults={
                'proficiency': min(data['proficiency'], 100.0),
                'source': 'course',
            }
        )
        
        if not created:
            # Update proficiency (cap at 100)
            user_skill.proficiency = min(user_skill.proficiency + data['proficiency'], 100.0)
            user_skill.last_practiced_at = timezone.now()
            user_skill.save(update_fields=['proficiency', 'last_practiced_at'])
        
        updated_skills.append(user_skill)
    
    return updated_skills


def get_skill_gaps(user, target_skills):
    """
    Identify skills user needs to learn
    Returns list of skills with current proficiency
    """
    user_skills = {
        us.skill_id: us.proficiency
        for us in UserSkill.objects.filter(user=user)
    }
    
    gaps = []
    for skill in target_skills:
        current_proficiency = user_skills.get(skill.id, 0.0)
        
        if current_proficiency < 80.0:  # Below mastery level
            gaps.append({
                'skill': skill,
                'current_proficiency': current_proficiency,
                'gap': 100.0 - current_proficiency,
                'priority': 'high' if current_proficiency == 0 else 'medium',
            })
    
    # Sort by proficiency (learn easier skills first)
    gaps.sort(key=lambda x: x['current_proficiency'])
    
    return gaps


def create_skill_gap_analysis(user, target_role, target_skill_names):
    """
    Create a skill gap analysis for a career goal
    """
    # Get or create skills
    target_skills = []
    for skill_name in target_skill_names:
        skill = create_skill(skill_name, category='technical')
        target_skills.append(skill)
    
    # Get current proficiency
    user_skills = {
        us.skill_id: us.proficiency
        for us in UserSkill.objects.filter(user=user)
    }
    
    # Calculate overall gap
    total_gap = 0.0
    priority_skills = []
    
    for skill in target_skills:
        current = user_skills.get(skill.id, 0.0)
        gap = 100.0 - current
        total_gap += gap
        
        if current < 50.0:  # Significant gap
            priority_skills.append({
                'skill_id': skill.id,
                'skill_name': skill.name,
                'current': current,
                'gap': gap,
            })
    
    avg_gap = total_gap / len(target_skills) if target_skills else 0.0
    
    # Estimate learning hours (10 hours per 10% proficiency gain)
    estimated_hours = int(total_gap / 10 * 10)
    
    # Create analysis
    analysis = SkillGapAnalysis.objects.create(
        user=user,
        target_role=target_role,
        gap_score=avg_gap,
        priority_skills=priority_skills,
        estimated_learning_hours=estimated_hours,
    )
    
    analysis.target_skills.set(target_skills)
    
    return analysis


# ===========================
# Recommendation Engine
# ===========================

def course_quality_score(course):
    """
    Calculate course quality score (0-1)
    Based on: completion rate, rating, enrollment count
    """
    enrollments = Enrollment.objects.filter(course=course).count()
    if enrollments == 0:
        return 0.5  # Neutral for new courses
    
    completions = Enrollment.objects.filter(
        course=course,
        is_completed=True
    ).count()
    
    completion_rate = completions / max(enrollments, 1)
    
    # Get average rating
    avg_rating = Review.objects.filter(course=course).aggregate(
        avg=django_models.Avg('rating')
    )['avg'] or 3.0
    
    # Normalize rating (0-1)
    rating_score = avg_rating / 5.0
    
    # Weighted score
    quality = (completion_rate * 0.5) + (rating_score * 0.4) + (min(enrollments / 100, 1) * 0.1)
    
    return quality


def find_similar_users(user, limit=20):
    """
    Find users with similar learning patterns
    Uses collaborative filtering based on course enrollments
    """
    # Get user's enrolled courses
    user_courses = set(
        Enrollment.objects.filter(user=user)
        .values_list('course_id', flat=True)
    )
    
    if not user_courses:
        return []
    
    # Find other users who enrolled in same courses
    similar_users = (
        Enrollment.objects
        .filter(course_id__in=user_courses)
        .exclude(user=user)
        .values('user')
        .annotate(overlap=Count('course_id'))
        .order_by('-overlap')[:limit]
    )
    
    return [item['user'] for item in similar_users]


def recommend_courses_collaborative(user, limit=10):
    """
    Collaborative filtering: Recommend courses that similar users enrolled in
    """
    # Get user's completed courses
    completed = set(
        Enrollment.objects.filter(user=user, is_completed=True)
        .values_list('course_id', flat=True)
    )
    
    enrolled = set(
        Enrollment.objects.filter(user=user)
        .values_list('course_id', flat=True)
    )
    
    # Find similar users
    similar_user_ids = find_similar_users(user)
    
    if not similar_user_ids:
        return []
    
    # Get courses enrolled by similar users
    candidate_courses = (
        Enrollment.objects
        .filter(user_id__in=similar_user_ids)
        .exclude(course_id__in=enrolled)
        .values('course')
        .annotate(popularity=Count('user'))
        .order_by('-popularity')[:limit * 3]
    )
    
    # Score and filter by quality
    recommendations = []
    for item in candidate_courses:
        course = Course.objects.get(id=item['course'])
        
        if course.status != 'published':
            continue
        
        quality = course_quality_score(course)
        
        if quality >= 0.4:  # Minimum quality threshold
            score = item['popularity'] * quality * 10
            
            recommendations.append({
                'course': course,
                'score': score,
                'algorithm': 'collaborative',
                'reason': f"Recommended because {item['popularity']} similar learners enrolled in this course",
            })
    
    # Sort by score
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    return recommendations[:limit]


def recommend_courses_content_based(user, limit=10):
    """
    Content-based filtering: Recommend courses based on user's skills and interests
    """
    # Get user's skills
    user_skills = UserSkill.objects.filter(user=user).select_related('skill')
    
    if not user_skills.exists():
        return []
    
    # Get user's interests
    interests = UserInterest.objects.filter(user=user).select_related('skill')
    interested_skills = {i.skill_id: i.interest_level for i in interests}
    
    # Get user's enrolled/completed courses
    enrolled = set(
        Enrollment.objects.filter(user=user)
        .values_list('course_id', flat=True)
    )
    
    # Find courses teaching skills user knows (for advancement)
    # and skills user is interested in
    relevant_skill_ids = [us.skill_id for us in user_skills]
    relevant_skill_ids.extend(interested_skills.keys())
    
    candidate_courses = (
        CourseSkill.objects
        .filter(skill_id__in=relevant_skill_ids)
        .exclude(course_id__in=enrolled)
        .exclude(course__status__in=['draft', 'archived', 'rejected'])
        .values('course')
        .annotate(
            relevance=Sum('weight'),
            skill_count=Count('skill')
        )
        .order_by('-relevance')[:limit * 3]
    )
    
    recommendations = []
    for item in candidate_courses:
        course = Course.objects.get(id=item['course'])
        
        quality = course_quality_score(course)
        
        if quality >= 0.4:
            # Calculate score based on skill relevance
            course_skills = CourseSkill.objects.filter(course=course).select_related('skill')
            
            relevance_score = 0.0
            matched_skills = []
            
            for cs in course_skills:
                if cs.skill_id in interested_skills:
                    relevance_score += cs.weight * interested_skills[cs.skill_id] * 2
                    matched_skills.append(cs.skill.name)
                elif cs.skill_id in relevant_skill_ids:
                    relevance_score += cs.weight
                    matched_skills.append(cs.skill.name)
            
            score = relevance_score * quality * 5
            
            recommendations.append({
                'course': course,
                'score': score,
                'algorithm': 'content_based',
                'reason': f"Matches your interests in {', '.join(matched_skills[:3])}",
                'matched_skills': matched_skills,
            })
    
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    return recommendations[:limit]


def recommend_courses_skill_gap(user, limit=10):
    """
    Recommend courses to fill user's skill gaps
    """
    # Get active skill gap analyses
    analyses = SkillGapAnalysis.objects.filter(
        user=user,
        is_active=True
    ).prefetch_related('target_skills')
    
    if not analyses.exists():
        return []
    
    # Get all target skills
    target_skill_ids = []
    for analysis in analyses:
        target_skill_ids.extend(analysis.target_skills.values_list('id', flat=True))
    
    # Get user's current skills
    user_skills = {
        us.skill_id: us.proficiency
        for us in UserSkill.objects.filter(user=user)
    }
    
    # Get enrolled courses
    enrolled = set(
        Enrollment.objects.filter(user=user)
        .values_list('course_id', flat=True)
    )
    
    # Find courses teaching needed skills
    candidate_courses = (
        CourseSkill.objects
        .filter(skill_id__in=target_skill_ids)
        .exclude(course_id__in=enrolled)
        .exclude(course__status__in=['draft', 'archived', 'rejected'])
        .values('course')
        .annotate(
            gap_fill_score=Sum('weight'),
            skill_count=Count('skill')
        )
        .order_by('-gap_fill_score')[:limit * 3]
    )
    
    recommendations = []
    for item in candidate_courses:
        course = Course.objects.get(id=item['course'])
        
        quality = course_quality_score(course)
        
        if quality >= 0.3:  # Lower threshold for gap-filling
            # Calculate how much this course fills gaps
            course_skills = CourseSkill.objects.filter(course=course).select_related('skill')
            
            gap_fill = 0.0
            filled_skills = []
            
            for cs in course_skills:
                if cs.skill_id in target_skill_ids:
                    current_prof = user_skills.get(cs.skill_id, 0.0)
                    gap = 100.0 - current_prof
                    gap_fill += (gap / 100.0) * cs.weight
                    filled_skills.append(cs.skill.name)
            
            score = gap_fill * quality * 15
            
            recommendations.append({
                'course': course,
                'score': score,
                'algorithm': 'skill_gap',
                'reason': f"Helps you learn {', '.join(filled_skills[:3])} for your career goal",
                'matched_skills': filled_skills,
            })
    
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    return recommendations[:limit]


def recommend_trending_courses(user=None, limit=10, days=7):
    """
    Recommend trending courses based on recent enrollments
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Find courses with high recent enrollment
    trending = (
        Enrollment.objects
        .filter(enrolled_at__gte=cutoff_date)
        .exclude(course__status__in=['draft', 'archived', 'rejected'])
        .values('course')
        .annotate(
            recent_enrollments=Count('id'),
            avg_rating=Avg('course__reviews__rating')
        )
        .order_by('-recent_enrollments')[:limit * 2]
    )
    
    # Exclude user's enrolled courses if user provided
    if user:
        enrolled = set(
            Enrollment.objects.filter(user=user)
            .values_list('course_id', flat=True)
        )
    else:
        enrolled = set()
    
    recommendations = []
    for item in trending:
        if item['course'] in enrolled:
            continue
        
        course = Course.objects.get(id=item['course'])
        
        quality = course_quality_score(course)
        
        score = item['recent_enrollments'] * quality * 5
        
        recommendations.append({
            'course': course,
            'score': score,
            'algorithm': 'trending',
            'reason': f"Trending now with {item['recent_enrollments']} recent enrollments",
        })
    
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    return recommendations[:limit]


def recommend_courses_hybrid(user, limit=10):
    """
    Hybrid recommendation: Combine multiple algorithms
    """
    all_recommendations = {}
    
    # Get recommendations from different algorithms
    collaborative = recommend_courses_collaborative(user, limit=5)
    content_based = recommend_courses_content_based(user, limit=5)
    skill_gap = recommend_courses_skill_gap(user, limit=5)
    trending = recommend_trending_courses(user, limit=3)
    
    # Combine and deduplicate
    for rec_list in [collaborative, content_based, skill_gap, trending]:
        for rec in rec_list:
            course_id = rec['course'].id
            
            if course_id not in all_recommendations:
                all_recommendations[course_id] = rec
            else:
                # Boost score if recommended by multiple algorithms
                all_recommendations[course_id]['score'] += rec['score'] * 0.5
                all_recommendations[course_id]['algorithm'] = 'hybrid'
    
    # Sort by score
    final_recommendations = sorted(
        all_recommendations.values(),
        key=lambda x: x['score'],
        reverse=True
    )
    
    return final_recommendations[:limit]


@transaction.atomic
def generate_recommendations(user, algorithm='hybrid', limit=10, save=True):
    """
    Generate and optionally save recommendations for a user
    """
    # Select algorithm
    if algorithm == 'collaborative':
        recs = recommend_courses_collaborative(user, limit)
    elif algorithm == 'content_based':
        recs = recommend_courses_content_based(user, limit)
    elif algorithm == 'skill_gap':
        recs = recommend_courses_skill_gap(user, limit)
    elif algorithm == 'trending':
        recs = recommend_trending_courses(user, limit)
    else:  # hybrid (default)
        recs = recommend_courses_hybrid(user, limit)
    
    if not save:
        return recs
    
    # Save to database
    created_recommendations = []
    
    for rec in recs:
        # Check if recommendation already exists
        existing = Recommendation.objects.filter(
            user=user,
            course=rec['course'],
            status='active'
        ).first()
        
        if existing:
            # Update score if changed significantly
            if abs(existing.score - rec['score']) > 10:
                existing.score = rec['score']
                existing.algorithm = rec['algorithm']
                existing.reason = rec['reason']
                existing.save(update_fields=['score', 'algorithm', 'reason'])
        else:
            # Create new recommendation
            recommendation = Recommendation.objects.create(
                user=user,
                course=rec['course'],
                score=rec['score'],
                algorithm=rec['algorithm'],
                reason=rec['reason'],
                expires_at=timezone.now() + timedelta(days=30)
            )
            
            # Add matched skills if available
            if 'matched_skills' in rec:
                skill_names = rec['matched_skills']
                skills = Skill.objects.filter(name__in=skill_names)
                recommendation.matched_skills.set(skills)
            
            created_recommendations.append(recommendation)
    
    return created_recommendations


# ===========================
# Trending Skills
# ===========================

def update_trending_skills(period_type='weekly'):
    """
    Calculate and update trending skills
    """
    if period_type == 'daily':
        days = 1
    elif period_type == 'monthly':
        days = 30
    else:  # weekly
        days = 7
    
    period_end = timezone.now().date()
    period_start = period_end - timedelta(days=days)
    
    # Get recent enrollments
    recent_enrollments = Enrollment.objects.filter(
        enrolled_at__date__gte=period_start,
        enrolled_at__date__lte=period_end
    )
    
    skill_stats = {}
    
    for enrollment in recent_enrollments:
        course_skills = CourseSkill.objects.filter(course=enrollment.course)
        
        for cs in course_skills:
            if cs.skill_id not in skill_stats:
                skill_stats[cs.skill_id] = {
                    'skill': cs.skill,
                    'enrollments': 0,
                    'completions': 0,
                }
            
            skill_stats[cs.skill_id]['enrollments'] += 1
            
            if enrollment.is_completed:
                skill_stats[cs.skill_id]['completions'] += 1
    
    # Calculate trend scores and create/update records
    trending_skills = []
    
    for rank, (skill_id, stats) in enumerate(
        sorted(skill_stats.items(), key=lambda x: x[1]['enrollments'], reverse=True),
        start=1
    ):
        # Calculate trend score (enrollment growth)
        trend_score = stats['enrollments'] * 1.0
        
        trending, created = TrendingSkill.objects.get_or_create(
            skill=stats['skill'],
            period_start=period_start,
            period_end=period_end,
            defaults={
                'period_type': period_type,
                'enrollment_count': stats['enrollments'],
                'completion_count': stats['completions'],
                'trend_score': trend_score,
                'rank': rank,
            }
        )
        
        if not created:
            old_rank = trending.rank
            trending.enrollment_count = stats['enrollments']
            trending.completion_count = stats['completions']
            trending.trend_score = trend_score
            trending.rank = rank
            trending.rank_change = old_rank - rank  # Positive = moved up
            trending.save()
        
        trending_skills.append(trending)
    
    # Update skill popularity scores
    for ts in trending_skills[:20]:  # Top 20
        ts.skill.popularity_score = ts.trend_score
        ts.skill.save(update_fields=['popularity_score'])
    
    return trending_skills


def get_trending_skills(period_type='weekly', limit=10):
    """
    Get current trending skills
    """
    # Get most recent period
    latest = TrendingSkill.objects.filter(
        period_type=period_type
    ).order_by('-period_end').first()
    
    if not latest:
        return []
    
    return TrendingSkill.objects.filter(
        period_type=period_type,
        period_start=latest.period_start,
        period_end=latest.period_end
    ).select_related('skill').order_by('rank')[:limit]


# ===========================
# Learning Paths
# ===========================

def create_learning_path(title, description, skill_names, course_ids, **kwargs):
    """
    Create a curated learning path
    """
    from django.utils.text import slugify
    
    slug = kwargs.get('slug') or slugify(title)
    
    path = LearningPath.objects.create(
        title=title,
        slug=slug,
        description=description,
        target_role=kwargs.get('target_role', ''),
        difficulty_level=kwargs.get('difficulty_level', 'beginner'),
        created_by=kwargs.get('created_by'),
        is_official=kwargs.get('is_official', False),
        is_published=kwargs.get('is_published', False),
        estimated_hours=kwargs.get('estimated_hours', 0),
        estimated_weeks=kwargs.get('estimated_weeks', 0),
    )
    
    # Add skills
    skills = []
    for skill_name in skill_names:
        skill = create_skill(skill_name, category='technical')
        skills.append(skill)
    path.required_skills.set(skills)
    
    # Add courses in order
    for order, course_id in enumerate(course_ids, start=1):
        course = Course.objects.get(id=course_id)
        PathCourse.objects.create(
            learning_path=path,
            course=course,
            order=order,
            is_required=True
        )
    
    return path


def enroll_in_learning_path(user, learning_path_id, target_date=None):
    """
    Enroll user in a learning path
    """
    learning_path = LearningPath.objects.get(id=learning_path_id)
    
    enrollment, created = UserLearningPath.objects.get_or_create(
        user=user,
        learning_path=learning_path,
        defaults={
            'target_completion_date': target_date,
        }
    )
    
    if created:
        learning_path.enrollment_count = F('enrollment_count') + 1
        learning_path.save(update_fields=['enrollment_count'])
    
    return enrollment


def update_learning_path_progress(user, learning_path):
    """
    Update user's progress in a learning path
    """
    enrollment = UserLearningPath.objects.get(
        user=user,
        learning_path=learning_path
    )
    
    # Get all required courses
    required_courses = PathCourse.objects.filter(
        learning_path=learning_path,
        is_required=True
    ).count()
    
    if required_courses == 0:
        return enrollment
    
    # Get completed courses
    completed_course_ids = enrollment.completed_courses.values_list('id', flat=True)
    completed_count = len(completed_course_ids)
    
    # Calculate progress
    progress = (completed_count / required_courses) * 100
    
    enrollment.progress = progress
    
    # Check if completed
    if progress >= 100 and not enrollment.completed_at:
        enrollment.completed_at = timezone.now()
        
        # Update path completion count
        learning_path.completion_count = F('completion_count') + 1
        learning_path.save(update_fields=['completion_count'])
    
    enrollment.save(update_fields=['progress', 'completed_at'])
    
    return enrollment
