from django.conf import settings
from django.test.runner import DiscoverRunner


class SourceDiscoverRunner(DiscoverRunner):
    """Resolve app labels to the project's separate test packages."""

    def build_suite(self, test_labels=None, **kwargs):
        tests = settings.REPOSITORY_DIR / "tests"
        labels = []
        for label in test_labels or [str(tests)]:
            app, separator, rest = label.partition(".")
            if app.isidentifier() and (tests / app / "__init__.py").is_file():
                label = f"tests.{app}{separator}{rest}"
            labels.append(label)
        return super().build_suite(labels, **kwargs)
