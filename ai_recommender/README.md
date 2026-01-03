# AI Recommender System - Complete Documentation

## Overview
Comprehensive AI-powered recommendation engine for the Skillstudio learning platform with multiple algorithms, skill tracking, gap analysis, and learning paths.

## Features

### Personalized Course Recommendations
- **Multiple Algorithms**: Collaborative filtering, content-based, skill gap analysis, hybrid
- **Smart Scoring**: Quality-based filtering with completion rate and ratings
- **Context-Aware**: Based on user skills, interests, and learning goals
- **Tracking**: Click tracking, dismissal, enrollment status

### Skill Management
- **Skill Taxonomy**: Categorized skills (technical, creative, business, etc.)
- **Proficiency Tracking**: 0-100% proficiency levels
- **Source Attribution**: Course completion, manual, assessment, imported
- **Popularity Scoring**: Trending skill detection

### Skill Gap Analysis
- **Career Path Mapping**: Define target roles and required skills
- **Gap Calculation**: Identify missing skills and proficiency gaps
- **Priority Ranking**: Focus on high-impact skills first
- **Progress Tracking**: Monitor skill acquisition over time
- **Learning Hour Estimates**: Calculate time to close gaps

### Learning Paths
- **Curated Paths**: Structured course sequences for specific goals
- **Official & Community**: Platform-curated and user-created paths
- **Progress Tracking**: Monitor completion across multiple courses
- **Skill Alignment**: Paths mapped to skill requirements
- **Difficulty Levels**: Beginner, intermediate, advanced

### Trending Analysis
- **Real-Time Trending**: Track popular skills by enrollment
- **Historical Tracking**: Weekly, monthly trend analysis
- **Rank Changes**: See rising and falling skills
- **Trend Scores**: Calculated growth metrics

### User Interests
- **Learning Goals**: Track what users want to learn
- **Interest Levels**: Prioritize high-interest topics
- **Deadlines**: Set target completion dates
- **Reasons**: Career change, hobby, job requirement, etc.

## Models

### Skill
Skills that can be learned through courses:
- Name, slug, category, description
- Popularity score (trending calculation)
- Active status
- Learner count property

### CourseSkill
Link courses to skills they teach:
- Course and skill relationship
- Weight (importance/depth: 0.1-10.0)
- Primary/secondary indicator
- Added by (instructor/admin/AI)

### UserSkill
Track user's skill proficiency:
- User and skill relationship
- Proficiency (0-100%)
- Source (course/manual/assessment/imported)
- First learned and last practiced timestamps

### UserInterest
User learning goals and interests:
- Skill interest with level (1-10)
- Reason (goal/career/hobby/job)
- Target proficiency
- Optional deadline

### Recommendation
AI-generated course recommendations:
- User and course relationship
- Score (0-100 confidence)
- Algorithm used
- Reason/explanation
- Matched skills (M2M)
- Status (active/dismissed/enrolled/expired)
- Click tracking
- Model version and metadata

### SkillGapAnalysis
Career path skill analysis:
- Target role and required skills
- Gap score (0-100%)
- Priority skills ranking
- Estimated learning hours
- Progress tracking

### TrendingSkill
Historical trending data:
- Skill and time period
- Enrollment/search/completion counts
- Trend score
- Rank and rank change

### LearningPath
Curated learning paths:
- Title, description, target role
- Difficulty level
- Required skills (M2M)
- Courses (through PathCourse)
- Estimated hours/weeks
- Official vs community
- Enrollment and completion stats

### PathCourse
Ordered courses in paths:
- Learning path and course
- Order position
- Required vs optional

### UserLearningPath
User path enrollment:
- User and path relationship
- Progress percentage
- Completed courses (M2M)
- Start and completion dates
- Target completion date

## API Endpoints

### Skill Endpoints
```
GET    /api/ai-recommender/skills/                 - List all skills
GET    /api/ai-recommender/skills/{slug}/          - Skill details
```

### User Skill Endpoints
```
GET    /api/ai-recommender/my-skills/              - List user skills
GET    /api/ai-recommender/my-skills/profile/      - Complete skill profile
POST   /api/ai-recommender/my-skills/update/       - Update skills from courses
```

### User Interest Endpoints
```
GET    /api/ai-recommender/interests/              - List interests
POST   /api/ai-recommender/interests/              - Create interest
GET    /api/ai-recommender/interests/{id}/         - Get interest
PUT    /api/ai-recommender/interests/{id}/         - Update interest
DELETE /api/ai-recommender/interests/{id}/         - Delete interest
```

### Recommendation Endpoints
```
GET    /api/ai-recommender/recommendations/                - List active recommendations
POST   /api/ai-recommender/recommendations/generate/       - Generate new recommendations
GET    /api/ai-recommender/recommendations/quick/          - Quick recommendations (no save)
GET    /api/ai-recommender/recommendations/{id}/           - Recommendation details
POST   /api/ai-recommender/recommendations/{id}/click/     - Track click
POST   /api/ai-recommender/recommendations/{id}/dismiss/   - Dismiss recommendation
```

### Skill Gap Analysis Endpoints
```
GET    /api/ai-recommender/skill-gaps/             - List analyses
POST   /api/ai-recommender/skill-gaps/create/      - Create analysis
GET    /api/ai-recommender/skill-gaps/{id}/        - Get analysis
DELETE /api/ai-recommender/skill-gaps/{id}/        - Delete analysis
```

### Trending Endpoints
```
GET    /api/ai-recommender/trending/skills/        - Get trending skills
POST   /api/ai-recommender/trending/skills/update/ - Update trending (admin)
```

### Learning Path Endpoints
```
GET    /api/ai-recommender/learning-paths/         - List paths
GET    /api/ai-recommender/learning-paths/{slug}/  - Path details
POST   /api/ai-recommender/learning-paths/enroll/  - Enroll in path
GET    /api/ai-recommender/my-learning-paths/      - My enrolled paths
```

## Usage Examples

### Creating Skills
```python
from ai_recommender import services

skill = services.create_skill(
    name='Python Programming',
    category='technical',
    description='Python language fundamentals'
)
```

### Adding Skills to Course
```python
services.add_skill_to_course(
    course=course,
    skill_name='Python Programming',
    weight=2.0,
    is_primary=True,
    added_by='instructor'
)
```

### Updating User Skills After Course Completion
```python
# Called automatically when course is completed
updated_skills = services.update_user_skills(user)
# Returns list of UserSkill objects with updated proficiency
```

### Generating Recommendations
```python
# Generate and save recommendations
recommendations = services.generate_recommendations(
    user=user,
    algorithm='hybrid',  # collaborative, content_based, skill_gap, trending
    limit=10,
    save=True
)

# Quick recommendations without saving
quick_recs = services.generate_recommendations(
    user=user,
    algorithm='collaborative',
    limit=5,
    save=False
)
```

### Creating Skill Gap Analysis
```python
analysis = services.create_skill_gap_analysis(
    user=user,
    target_role='Full Stack Developer',
    target_skill_names=['Python', 'Django', 'React', 'PostgreSQL']
)

print(f"Gap Score: {analysis.gap_score}%")
print(f"Estimated Hours: {analysis.estimated_learning_hours}")
print(f"Priority Skills: {analysis.priority_skills}")
```

### Creating Learning Path
```python
path = services.create_learning_path(
    title='Python Developer Bootcamp',
    description='Complete path to becoming a Python developer',
    skill_names=['Python', 'Django', 'PostgreSQL', 'REST APIs'],
    course_ids=[1, 2, 3, 4, 5],
    difficulty_level='beginner',
    estimated_hours=120,
    estimated_weeks=12,
    is_official=True,
    is_published=True
)
```

### Enrolling in Learning Path
```python
enrollment = services.enroll_in_learning_path(
    user=user,
    learning_path_id=path.id,
    target_date=date(2026, 6, 1)
)
```

### Updating Learning Path Progress
```python
# Called when user completes a course in the path
services.update_learning_path_progress(user, learning_path)
```

### Tracking Trending Skills
```python
# Update trending (run periodically via cron)
trending = services.update_trending_skills(period_type='weekly')

# Get current trending
trending_skills = services.get_trending_skills(
    period_type='weekly',
    limit=10
)
```

## Recommendation Algorithms

### Collaborative Filtering
Recommends courses based on similar users' enrollments:
1. Find users with overlapping course enrollments
2. Get courses they enrolled in that current user hasn't
3. Score by popularity among similar users
4. Filter by quality threshold

### Content-Based Filtering
Recommends courses matching user's skills and interests:
1. Analyze user's current skills
2. Consider declared interests
3. Find courses teaching relevant skills
4. Score by skill relevance and interest level
5. Filter by quality

### Skill Gap Analysis
Recommends courses to fill identified skill gaps:
1. Get user's skill gap analyses
2. Find courses teaching needed skills
3. Score by gap-filling potential
4. Prioritize high-impact skills

### Trending
Recommends currently popular courses:
1. Find courses with high recent enrollment
2. Filter by quality
3. Exclude user's enrolled courses

### Hybrid (Default)
Combines all algorithms:
1. Run all algorithms with smaller limits
2. Combine and deduplicate results
3. Boost scores for multi-algorithm matches
4. Sort by final combined score

## Business Logic

### Proficiency Calculation
- **Primary Skills**: +15 points per course completion
- **Secondary Skills**: +10 points per course completion
- **Weighted by importance**: Multiplied by skill weight
- **Capped at 100%**: Maximum proficiency level

### Quality Score Formula
```
quality = (completion_rate * 0.5) + (rating_score * 0.4) + (popularity * 0.1)
```
- Completion rate: 50% weight
- Average rating: 40% weight (normalized 0-1)
- Popularity: 10% weight (enrollments/100, capped at 1)

### Gap Score Calculation
```
gap_score = average(100 - current_proficiency for each target skill)
```
- 0% = No gap (all skills mastered)
- 100% = Complete gap (no skills learned)

### Learning Hour Estimation
```
hours = sum(gap for each skill) / 10 * 10
```
- 10 hours per 10% proficiency gain per skill

## Database Indexes

Optimized for performance:
- **Skill**: name, category+popularity, active+popularity
- **CourseSkill**: course+weight, skill+weight
- **UserSkill**: user+proficiency, skill+proficiency
- **UserInterest**: user+interest_level
- **Recommendation**: user+status+score, user+created, algorithm+score
- **SkillGapAnalysis**: user+active
- **TrendingSkill**: period_end+rank, skill+period_end
- **LearningPath**: published+enrollment_count

## Testing

Run tests:
```bash
python manage.py test ai_recommender --verbosity=2
```

Test coverage:
- ✅ Model creation and validation
- ✅ Service functions
- ✅ Recommendation algorithms
- ✅ Skill tracking and updates
- ✅ API endpoints
- ✅ Permission checks

## Admin Interface

Django admin configured for all models:
- Skills with category filters
- Course-skill mappings
- User skills with proficiency colors
- Recommendations with status badges
- Skill gap analyses
- Trending skills with rankings
- Learning paths with completion rates

Access at: `/admin/ai_recommender/`

## Migration

Create migrations:
```bash
python manage.py makemigrations ai_recommender
python manage.py migrate ai_recommender
```

## Scheduled Tasks

### Update Trending Skills
Run weekly via cron:
```bash
python manage.py shell -c "from ai_recommender.services import update_trending_skills; update_trending_skills('weekly')"
```

### Generate Recommendations
Run daily for active users:
```python
from ai_recommender.services import generate_recommendations
from accounts.models import User

for user in User.objects.filter(is_active=True):
    generate_recommendations(user, algorithm='hybrid', limit=10, save=True)
```

### Update Skill Proficiency
Triggered automatically on:
- Course completion
- Assessment completion
- Manual skill updates

## Integration Points

### With Enrollments
- Auto-update user skills on course completion
- Track completion for skill proficiency
- Recommend next courses based on progress

### With Courses
- Course-skill mapping for content-based recommendations
- Quality scoring using enrollment and completion data
- Skill-based filtering and search

### With Social (Reviews)
- Quality scoring incorporates review ratings
- Helpful reviews boost course recommendations

### With Analytics
- Track recommendation click-through rates
- Monitor algorithm performance
- Analyze skill popularity trends

## Future Enhancements

- [ ] Machine learning model integration
- [ ] Natural language processing for skill extraction
- [ ] Personalized learning pace recommendations
- [ ] Skill prerequisite mapping
- [ ] Automated skill level assessment
- [ ] Career path visualization
- [ ] Peer skill comparisons
- [ ] Skill endorsements
- [ ] Integration with job market data
- [ ] Advanced analytics dashboard

## Configuration

```python
# services.py constants
PLATFORM_FEE_RATE = Decimal("0.20")  # Not used in recommender
SKILL_PROFICIENCY_CAP = 100.0
QUALITY_THRESHOLD = 0.4
PRIMARY_SKILL_POINTS = 15
SECONDARY_SKILL_POINTS = 10
```

## Support

For issues or questions:
- Check test cases for usage examples
- Review service function docstrings
- Examine model properties and methods
- Test in admin interface first
- Review recommendation algorithm logic
