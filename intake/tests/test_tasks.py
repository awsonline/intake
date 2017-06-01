from django.test import TestCase, override_settings
from intake import tasks
from user_accounts.tests.factories import FakeOrganizationFactory
from user_accounts.models import Organization
from celery.result import AsyncResult


class TestGetOrg(TestCase):

    # this changes task result types to EagerResult, a subclass of AsyncResult
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_calls_celery_properly(self):
        org = FakeOrganizationFactory()
        new_slug = 'changed'
        async_result = tasks.set_slug.delay(org.slug, new_slug)
        self.assertTrue(isinstance(async_result, AsyncResult))
        # because this was set to 'eager', this works
        # if we didn't have an eager, .get() would raise an error
        # and the org instance would not yet reflect the async changes
        final_result = async_result.get()
        self.assertEqual(final_result, org)
        org = Organization.objects.get(id=org.id)
        self.assertEqual(org.slug, new_slug)
