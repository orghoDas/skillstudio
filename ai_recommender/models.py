from django.db import models
from django.conf import settings

# Create your models here.


# PostgreSQL Equivalent:
# CREATE TABLE ai_recommender_skillprofile (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER UNIQUE NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     skills JSONB DEFAULT '[]',
#     last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX ai_recommender_skillprofile_user_id_idx ON ai_recommender_skillprofile(user_id);
class SkillProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    skills = models.JSONField(default=list, blank=True)
    last_updated = models.DateTimeField(auto_now=True)


# PostgreSQL Equivalent:
# CREATE TABLE ai_recommender_recommendation (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     score DOUBLE PRECISION NOT NULL,
#     reason TEXT,
#     model_version VARCHAR(50),
#     recommended_course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX ai_recommender_recommendation_user_id_idx ON ai_recommender_recommendation(user_id);
# CREATE INDEX ai_recommender_recommendation_course_id_idx ON ai_recommender_recommendation(recommended_course_id);
class Recommendation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations")
    score = models.FloatField()
    reason = models.TextField(blank=True, null=True)
    model_version = models.CharField(max_length=50, blank=True, null=True)
    recommended_course = models.ForeignKey("courses.Course", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


# PostgreSQL Equivalent:
# CREATE TABLE ai_recommender_embedding (
#     id SERIAL PRIMARY KEY,
#     entity_type VARCHAR(50) NOT NULL,
#     entity_id BIGINT NOT NULL,
#     vector BYTEA NOT NULL,
#     meta JSONB DEFAULT '{}',
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX ai_recommender_embedding_entity_type_idx ON ai_recommender_embedding(entity_type);
# CREATE INDEX ai_recommender_embedding_entity_id_idx ON ai_recommender_embedding(entity_id);
class Embedding(models.Model):
    entity_type = models.CharField(max_length=50)
    entity_id = models.BigIntegerField()
    vector = models.BinaryField()
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

