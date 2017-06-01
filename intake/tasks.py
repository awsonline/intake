from celery import shared_task
from requests import request
from user_accounts.models import Organization


@shared_task
def celery_request(*args, **kwargs):
    request(*args, **kwargs)


@shared_task
def set_slug(old_slug, new_slug):
    org = Organization.objects.get(slug=old_slug)
    org.slug = new_slug
    org.save()
    return org
