import statistics
from pprint import pprint
from intake.models import StatusUpdate
from user_accounts.models import Organization


def responsiveness_of_org(org):
    response_times = []
    update_count = StatusUpdate.objects.filter(
        application__organization=org).count()
    for app in org.applications.all():
        first_update = app.status_updates.order_by('created').first()
        if first_update:
            response_time = first_update.created - app.created
            response_times.append(response_time.days)
    if len(response_times) > 1:
        return dict(
            mean=statistics.mean(response_times),
            median=statistics.median(response_times),
            max=max(response_times),
            min=min(response_times),
            number_of_updates=update_count)
    else:
        return "Not enough status updates"


def org_report():
    for org in Organization.objects.all():
        print(org.name)
        pprint(
            responsiveness_of_org(org))
