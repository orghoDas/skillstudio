from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = settings.AUTH_USER_MODEL


class Skill(models.Model):
    """Skills that can be learned through courses"""
    
    CATEGORY_CHOICES = [
        ('technical', 'Technical'),
        ('creative', 'Creative'),
        ('business', 'Business'),
        ('language', 'Language'),
        ('personal', 'Personal Development'),
        ('science', 'Science & Math'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(max_length=120, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    popularity_score = models.FloatField(default=0.0, help_text="Calculated based on course enrollments")
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-popularity_score', 'name']
        indexes = [
            models.Index(fields=['category', '-popularity_score']),
            models.Index(fields=['is_active', '-popularity_score']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def learner_count(self):
        """Count of users learning this skill"""
        return self.user_skills.count()


class CourseSkill(models.Model):
    """Link courses to skills they teach"""
    
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='course_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='course_mappings')
    
    weight = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(10.0)],
        help_text="Importance of this skill in the course (1.0 = primary, 0.5 = secondary)"
    )
    
    # Instructor-defined or auto-detected
    is_primary = models.BooleanField(default=False, help_text="Is this a primary learning outcome?")
    added_by = models.CharField(max_length=50, default='instructor', choices=[
        ('instructor', 'Instructor'),
        ('admin', 'Admin'),
        ('ai', 'AI Detected'),
    ])
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('course', 'skill')
        ordering = ['-weight', '-is_primary']
        indexes = [
            models.Index(fields=['course', '-weight']),
            models.Index(fields=['skill', '-weight']),
        ]
    
    def __str__(self):
        return f"{self.course.title} - {self.skill.name} ({self.weight})"


class UserSkill(models.Model):
    """Track user's skill proficiency levels"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='user_skills')
    
    proficiency = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Skill level: 0-100"
    )
    
    # How was this skill acquired?
    source = models.CharField(max_length=50, default='course', choices=[
        ('course', 'Course Completion'),
        ('manual', 'Self-Reported'),
        ('assessment', 'Assessment Result'),
        ('imported', 'Imported Profile'),
    ])
    
    # Timestamps
    first_learned_at = models.DateTimeField(default=timezone.now)
    last_practiced_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('user', 'skill')
        ordering = ['-proficiency', '-last_practiced_at']
        indexes = [
            models.Index(fields=['user', '-proficiency']),
            models.Index(fields=['skill', '-proficiency']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.skill.name} ({self.proficiency}%)"


class UserInterest(models.Model):
    """Track user interests and learning goals"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interests')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='interested_users')
    
    interest_level = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(10.0)],
        help_text="How interested is the user? (1.0 = normal, 5.0 = very interested)"
    )
    
    reason = models.CharField(max_length=50, default='learning_goal', choices=[
        ('learning_goal', 'Learning Goal'),
        ('career_change', 'Career Change'),
        ('hobby', 'Hobby/Personal Interest'),
        ('job_requirement', 'Job Requirement'),
        ('recommendation', 'Recommended'),
    ])
    
    target_proficiency = models.FloatField(
        default=50.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Desired proficiency level"
    )
    
    deadline = models.DateField(null=True, blank=True, help_text="Target completion date")
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'skill')
        ordering = ['-interest_level', '-created_at']
        indexes = [
            models.Index(fields=['user', '-interest_level']),
        ]
    
    def __str__(self):
        return f"{self.user.email} interested in {self.skill.name}"


class Recommendation(models.Model):
    """AI-generated course recommendations for users"""
    
    ALGORITHM_CHOICES = [
        ('collaborative', 'Collaborative Filtering'),
        ('content_based', 'Content-Based'),
        ('hybrid', 'Hybrid'),
        ('skill_gap', 'Skill Gap Analysis'),
        ('trending', 'Trending'),
        ('similar_users', 'Similar Users'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dismissed', 'Dismissed'),
        ('enrolled', 'Enrolled'),
        ('expired', 'Expired'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendations')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='recommendations')
    
    # Recommendation details
    score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Recommendation confidence score (0-100)"
    )
    algorithm = models.CharField(max_length=50, choices=ALGORITHM_CHOICES)
    reason = models.TextField(help_text="Why this course was recommended")
    
    # Related data
    matched_skills = models.ManyToManyField(Skill, blank=True, related_name='recommendations')
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    clicked = models.BooleanField(default=False)
    clicked_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    model_version = models.CharField(max_length=50, default='v1.0')
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional algorithm-specific data")
    
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When recommendation becomes stale")
    
    class Meta:
        ordering = ['-score', '-created_at']
        indexes = [
            models.Index(fields=['user', 'status', '-score']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['algorithm', '-score']),
        ]
    
    def __str__(self):
        return f"{self.course.title} recommended to {self.user.email} ({self.score:.1f})"
    
    def mark_clicked(self):
        """Track when user clicks on recommendation"""
        if not self.clicked:
            self.clicked = True
            self.clicked_at = timezone.now()
            self.save(update_fields=['clicked', 'clicked_at'])
    
    def dismiss(self):
        """User dismissed this recommendation"""
        self.status = 'dismissed'
        self.save(update_fields=['status'])
    
    def mark_enrolled(self):
        """User enrolled in recommended course"""
        self.status = 'enrolled'
        self.save(update_fields=['status'])


class SkillGapAnalysis(models.Model):
    """Track skill gap analysis for career paths"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skill_gaps')
    
    target_role = models.CharField(max_length=200, help_text="Target job title or career goal")
    target_skills = models.ManyToManyField(Skill, related_name='required_for_roles')
    
    # Analysis results
    gap_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Overall skill gap (0 = no gap, 100 = complete gap)"
    )
    
    priority_skills = models.JSONField(default=list, help_text="List of skills to focus on first")
    estimated_learning_hours = models.IntegerField(default=0, help_text="Estimated time to close gap")
    
    # Status
    is_active = models.BooleanField(default=True)
    progress = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_analyzed_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Skill Gap Analysis"
        verbose_name_plural = "Skill Gap Analyses"
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.target_role} (Gap: {self.gap_score:.1f}%)"


class TrendingSkill(models.Model):
    """Track trending skills over time"""
    
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='trending_data')
    
    # Time period
    period_start = models.DateField()
    period_end = models.DateField()
    period_type = models.CharField(max_length=20, default='weekly', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ])
    
    # Metrics
    enrollment_count = models.IntegerField(default=0)
    search_count = models.IntegerField(default=0)
    completion_count = models.IntegerField(default=0)
    
    trend_score = models.FloatField(
        default=0.0,
        help_text="Calculated trend score based on growth rate"
    )
    
    rank = models.IntegerField(default=0, help_text="Ranking in trending list")
    rank_change = models.IntegerField(default=0, help_text="Change from previous period")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_end', 'rank']
        unique_together = ('skill', 'period_start', 'period_end')
        indexes = [
            models.Index(fields=['-period_end', 'rank']),
            models.Index(fields=['skill', '-period_end']),
        ]
    
    def __str__(self):
        return f"{self.skill.name} - #{self.rank} ({self.period_end})"


class LearningPath(models.Model):
    """Curated learning paths for specific goals"""
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    
    # Target audience
    target_role = models.CharField(max_length=200, blank=True)
    difficulty_level = models.CharField(max_length=20, default='beginner', choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ])
    
    # Path details
    required_skills = models.ManyToManyField(Skill, related_name='learning_paths')
    courses = models.ManyToManyField('courses.Course', through='PathCourse', related_name='learning_paths')
    
    estimated_hours = models.IntegerField(default=0)
    estimated_weeks = models.IntegerField(default=0)
    
    # Curation
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_paths')
    is_official = models.BooleanField(default=False, help_text="Curated by platform")
    is_published = models.BooleanField(default=False)
    
    # Stats
    enrollment_count = models.IntegerField(default=0)
    completion_count = models.IntegerField(default=0)
    avg_rating = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_official', '-enrollment_count']
        indexes = [
            models.Index(fields=['is_published', '-enrollment_count']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def completion_rate(self):
        """Calculate completion rate"""
        if self.enrollment_count == 0:
            return 0.0
        return (self.completion_count / self.enrollment_count) * 100


class PathCourse(models.Model):
    """Ordered courses in a learning path"""
    
    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name='path_courses')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    
    order = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ('learning_path', 'course')
    
    def __str__(self):
        return f"{self.learning_path.title} - {self.course.title} (#{self.order})"


class UserLearningPath(models.Model):
    """Track user enrollment in learning paths"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrolled_paths')
    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name='enrollments')
    
    progress = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    completed_courses = models.ManyToManyField('courses.Course', blank=True, related_name='path_completions')
    
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    target_completion_date = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ('user', 'learning_path')
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.learning_path.title} ({self.progress:.1f}%)"


# PostgreSQL equivalents for AI recommender models (summarized):
# CREATE TABLE IF NOT EXISTS ai_recommender_skill (
#     id serial PRIMARY KEY,
#     name varchar(100) NOT NULL UNIQUE,
#     slug varchar(120) NOT NULL UNIQUE,
#     category varchar(50) NOT NULL DEFAULT 'other',
#     description text NOT NULL DEFAULT '',
#     is_active boolean NOT NULL DEFAULT true,
#     popularity_score double precision NOT NULL DEFAULT 0.0,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now()
# );
# CREATE INDEX IF NOT EXISTS idx_ai_recommender_skill_category_popularity ON ai_recommender_skill (category, popularity_score DESC);

# CREATE TABLE IF NOT EXISTS ai_recommender_courseskill (
#     id serial PRIMARY KEY,
#     course_id integer NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     skill_id integer NOT NULL REFERENCES ai_recommender_skill(id) ON DELETE CASCADE,
#     weight double precision NOT NULL DEFAULT 1.0,
#     is_primary boolean NOT NULL DEFAULT false,
#     added_by varchar(50) NOT NULL DEFAULT 'instructor',
#     created_at timestamptz NOT NULL DEFAULT now(),
#     UNIQUE (course_id, skill_id)
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_userskill (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     skill_id integer NOT NULL REFERENCES ai_recommender_skill(id) ON DELETE CASCADE,
#     proficiency double precision NOT NULL DEFAULT 0.0,
#     source varchar(50) NOT NULL DEFAULT 'course',
#     first_learned_at timestamptz NOT NULL DEFAULT now(),
#     last_practiced_at timestamptz NOT NULL DEFAULT now(),
#     UNIQUE (user_id, skill_id)
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_userinterest (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     skill_id integer NOT NULL REFERENCES ai_recommender_skill(id) ON DELETE CASCADE,
#     interest_level double precision NOT NULL DEFAULT 1.0,
#     reason varchar(50) NOT NULL DEFAULT 'learning_goal',
#     target_proficiency double precision NOT NULL DEFAULT 50.0,
#     deadline date NULL,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now(),
#     UNIQUE (user_id, skill_id)
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_recommendation (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     course_id integer NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     score double precision NOT NULL,
#     algorithm varchar(50) NOT NULL,
#     reason text NOT NULL,
#     status varchar(20) NOT NULL DEFAULT 'active',
#     clicked boolean NOT NULL DEFAULT false,
#     clicked_at timestamptz NULL,
#     model_version varchar(50) NOT NULL DEFAULT 'v1.0',
#     metadata jsonb NOT NULL DEFAULT '{}',
#     created_at timestamptz NOT NULL DEFAULT now(),
#     expires_at timestamptz NULL
# );
# -- M2M table for matched_skills
# CREATE TABLE IF NOT EXISTS ai_recommender_recommendation_matched_skills (
#     id serial PRIMARY KEY,
#     recommendation_id integer NOT NULL REFERENCES ai_recommender_recommendation(id) ON DELETE CASCADE,
#     skill_id integer NOT NULL REFERENCES ai_recommender_skill(id) ON DELETE CASCADE
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_skillgapanalysis (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     target_role varchar(200) NOT NULL,
#     gap_score double precision NOT NULL DEFAULT 0.0,
#     priority_skills jsonb NOT NULL DEFAULT '[]',
#     estimated_learning_hours integer NOT NULL DEFAULT 0,
#     is_active boolean NOT NULL DEFAULT true,
#     progress double precision NOT NULL DEFAULT 0.0,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now(),
#     last_analyzed_at timestamptz NOT NULL DEFAULT now()
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_trendingskill (
#     id serial PRIMARY KEY,
#     skill_id integer NOT NULL REFERENCES ai_recommender_skill(id) ON DELETE CASCADE,
#     period_start date NOT NULL,
#     period_end date NOT NULL,
#     period_type varchar(20) NOT NULL DEFAULT 'weekly',
#     enrollment_count integer NOT NULL DEFAULT 0,
#     search_count integer NOT NULL DEFAULT 0,
#     completion_count integer NOT NULL DEFAULT 0,
#     trend_score double precision NOT NULL DEFAULT 0.0,
#     rank integer NOT NULL DEFAULT 0,
#     rank_change integer NOT NULL DEFAULT 0,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     UNIQUE (skill_id, period_start, period_end)
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_learningpath (
#     id serial PRIMARY KEY,
#     title varchar(200) NOT NULL,
#     slug varchar(220) NOT NULL UNIQUE,
#     description text NOT NULL,
#     target_role varchar(200) NULL,
#     difficulty_level varchar(20) NOT NULL DEFAULT 'beginner',
#     estimated_hours integer NOT NULL DEFAULT 0,
#     estimated_weeks integer NOT NULL DEFAULT 0,
#     created_by_id integer NULL REFERENCES accounts_user(id) ON DELETE SET NULL,
#     is_official boolean NOT NULL DEFAULT false,
#     is_published boolean NOT NULL DEFAULT false,
#     enrollment_count integer NOT NULL DEFAULT 0,
#     completion_count integer NOT NULL DEFAULT 0,
#     avg_rating double precision NOT NULL DEFAULT 0.0,
#     created_at timestamptz NOT NULL DEFAULT now(),
#     updated_at timestamptz NOT NULL DEFAULT now()
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_pathcourse (
#     id serial PRIMARY KEY,
#     learning_path_id integer NOT NULL REFERENCES ai_recommender_learningpath(id) ON DELETE CASCADE,
#     course_id integer NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     order integer NOT NULL DEFAULT 0,
#     is_required boolean NOT NULL DEFAULT true,
#     UNIQUE (learning_path_id, course_id)
# );

# CREATE TABLE IF NOT EXISTS ai_recommender_userlearningpath (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     learning_path_id integer NOT NULL REFERENCES ai_recommender_learningpath(id) ON DELETE CASCADE,
#     progress double precision NOT NULL DEFAULT 0.0,
#     started_at timestamptz NOT NULL DEFAULT now(),
#     completed_at timestamptz NULL,
#     target_completion_date date NULL,
#     UNIQUE (user_id, learning_path_id)
# );
