from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ("user","course")


class Forum(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="forums", null=True, blank=True)
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)


class Thread(models.Model):
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="threads")
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)


class Post(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="posts")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)



class LearningCircle(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    course = models.ForeignKey("courses.Course", on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_circles")
    created_at = models.DateTimeField(default=timezone.now)


class CircleMembership(models.Model):
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(default=timezone.now)
    class Meta:
        unique_together = ("circle","user")


class CircleMessage(models.Model):
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
