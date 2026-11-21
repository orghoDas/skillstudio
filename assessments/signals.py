"""Keep Quiz.total_marks equal to the sum of its questions' marks (ASM-04).

Fires for every write path (quiz editor, admin, shell), so the stored total
can't drift from the questions.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Quiz, QuizQuestion


@receiver(post_save, sender=QuizQuestion)
@receiver(post_delete, sender=QuizQuestion)
def sync_quiz_total_marks(sender, instance, **kwargs):
    quiz = Quiz.objects.filter(pk=instance.quiz_id).first()
    if quiz is not None:  # None while the quiz itself is being deleted
        quiz.refresh_total_marks()
