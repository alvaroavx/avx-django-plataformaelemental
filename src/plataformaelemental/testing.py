from django.conf import settings
from django.test.runner import DiscoverRunner


class SourceDiscoverRunner(DiscoverRunner):
    """Discover tests under src, including when old app directories remain."""

    def build_suite(self, test_labels=None, **kwargs):
        source = settings.SOURCE_DIR
        labels = [
            str(source / label) if label.isidentifier() and (source / label / "__init__.py").is_file() else label
            for label in test_labels or [str(source)]
        ]
        return super().build_suite(labels, **kwargs)
