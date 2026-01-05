from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from ai_recommender.services import generate_recommendations_for_user
from ai_recommender.models import Recommendation

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate recommendations for a user or for all users'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, help='Generate recommendations for a specific user id')
        parser.add_argument('--top-n', type=int, default=10, help='Number of recommendations to keep')

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        top_n = options.get('top_n')

        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                raise CommandError(f'User {user_id} does not exist')
            recs = generate_recommendations_for_user(user, top_n=top_n)
            self.stdout.write(self.style.SUCCESS(f'Generated {len(recs)} recommendations for user {user_id}'))
            return

        count = 0
        for user in User.objects.all():
            recs = generate_recommendations_for_user(user, top_n=top_n)
            count += len(recs)
        self.stdout.write(self.style.SUCCESS(f'Generated {count} recommendations for all users'))
