from django.test.runner import DiscoverRunner


class BarTechTestRunner(DiscoverRunner):
    def build_suite(self, test_labels=None, **kwargs):
        if not test_labels:
            test_labels = ['catalog']
        return super().build_suite(test_labels, **kwargs)