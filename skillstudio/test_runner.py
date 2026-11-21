"""Project test runner (OPS-02 / TEST-01).

* Every test run gets its own temporary MEDIA_ROOT, deleted afterwards, so
  tests that generate certificate PDFs never write into the real media/
  folder.
* Refuses to run against a non-local database (OPS-05); settings.py already
  points tests at SQLite unless TEST_DATABASE_URL is set.
* Static files use plain StaticFilesStorage during tests: Django runs tests
  with DEBUG=False, where the production manifest storage would require a
  prior `collectstatic` just to render a page that uses {% static %}.
"""

import os
import shutil
import tempfile

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


LOCAL_DB_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


class SkillStudioTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        # OPS-05: never create/destroy test databases on a remote server by accident.
        from django.conf import settings

        for alias, config in settings.DATABASES.items():
            host = (config.get("HOST") or "").strip()
            if host not in LOCAL_DB_HOSTS and os.getenv("ALLOW_REMOTE_TEST_DATABASE") != "1":
                raise RuntimeError(
                    f"Refusing to run tests against remote database host {host!r} (alias {alias!r}). "
                    "Unset TEST_DATABASE_URL to use local SQLite, or set ALLOW_REMOTE_TEST_DATABASE=1."
                )
        return super().setup_databases(**kwargs)

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_root = tempfile.mkdtemp(prefix="skillstudio-test-media-")
        self._isolation = override_settings(
            MEDIA_ROOT=self._media_root,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        )
        self._isolation.enable()

    def teardown_test_environment(self, **kwargs):
        self._isolation.disable()
        shutil.rmtree(self._media_root, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
