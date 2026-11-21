from django.core.management.base import BaseCommand

from core.routes import DOC_PATH, render_routes


class Command(BaseCommand):
    help = "Print the API route reference, or write it to docs/API_ROUTES.md with --write."

    def add_arguments(self, parser):
        parser.add_argument("--write", action="store_true", help=f"write {DOC_PATH.name}")

    def handle(self, *args, write=False, **options):
        text = render_routes()
        if write:
            DOC_PATH.parent.mkdir(exist_ok=True)
            DOC_PATH.write_text(text)
            self.stdout.write(self.style.SUCCESS(f"Wrote {DOC_PATH}"))
        else:
            self.stdout.write(text, ending="")
