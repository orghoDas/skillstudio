from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# PostgreSQL Equivalent:
# CREATE TABLE social_review (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     rating SMALLINT NOT NULL CHECK (rating >= 0),
#     title VARCHAR(255) DEFAULT '',
#     comment TEXT DEFAULT '',
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     UNIQUE (user_id, course_id)
# );
# CREATE INDEX social_review_user_id_idx ON social_review(user_id);
# CREATE INDEX social_review_course_id_idx ON social_review(course_id);
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ("user","course")


# PostgreSQL Equivalent:
# CREATE TABLE social_forum (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER REFERENCES courses_course(id) ON DELETE CASCADE,
#     title VARCHAR(255) NOT NULL,
#     created_by_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX social_forum_course_id_idx ON social_forum(course_id);
# CREATE INDEX social_forum_created_by_id_idx ON social_forum(created_by_id);
class Forum(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="forums", null=True, blank=True)
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)


# PostgreSQL Equivalent:
# CREATE TABLE social_thread (
#     id SERIAL PRIMARY KEY,
#     forum_id INTEGER NOT NULL REFERENCES social_forum(id) ON DELETE CASCADE,
#     title VARCHAR(255) NOT NULL,
#     created_by_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX social_thread_forum_id_idx ON social_thread(forum_id);
# CREATE INDEX social_thread_created_by_id_idx ON social_thread(created_by_id);
class Thread(models.Model):
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="threads")
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)


# PostgreSQL Equivalent:
# CREATE TABLE social_post (
#     id SERIAL PRIMARY KEY,
#     thread_id INTEGER NOT NULL REFERENCES social_thread(id) ON DELETE CASCADE,
#     user_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     content TEXT NOT NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     edited_at TIMESTAMP WITH TIME ZONE
# );
# CREATE INDEX social_post_thread_id_idx ON social_post(thread_id);
# CREATE INDEX social_post_user_id_idx ON social_post(user_id);
class Post(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="posts")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)



# PostgreSQL Equivalent:
# CREATE TABLE social_learningcircle (
#     id SERIAL PRIMARY KEY,
#     name VARCHAR(255) NOT NULL,
#     description TEXT DEFAULT '',
#     course_id INTEGER REFERENCES courses_course(id) ON DELETE SET NULL,
#     created_by_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX social_learningcircle_course_id_idx ON social_learningcircle(course_id);
# CREATE INDEX social_learningcircle_created_by_id_idx ON social_learningcircle(created_by_id);
class LearningCircle(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    course = models.ForeignKey("courses.Course", on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_circles")
    created_at = models.DateTimeField(default=timezone.now)


# PostgreSQL Equivalent:
# CREATE TABLE social_circlemembership (
#     id SERIAL PRIMARY KEY,
#     circle_id INTEGER NOT NULL REFERENCES social_learningcircle(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     UNIQUE (circle_id, user_id)
# );
# CREATE INDEX social_circlemembership_circle_id_idx ON social_circlemembership(circle_id);
# CREATE INDEX social_circlemembership_user_id_idx ON social_circlemembership(user_id);
class CircleMembership(models.Model):
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ("circle","user")


# PostgreSQL Equivalent:
# CREATE TABLE social_circlemessage (
#     id SERIAL PRIMARY KEY,
#     circle_id INTEGER NOT NULL REFERENCES social_learningcircle(id) ON DELETE CASCADE,
#     user_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     message TEXT NOT NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX social_circlemessage_circle_id_idx ON social_circlemessage(circle_id);
# CREATE INDEX social_circlemessage_user_id_idx ON social_circlemessage(user_id);
class CircleMessage(models.Model):
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
