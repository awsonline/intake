import statistics
from intake.models import FormSubmission


def ages_of_applicants():
    answers = FormSubmission.objects.values_list('answers', flat=True)
    ages = []
    for datum in answers:
        year = None
        try:
            year = answers.get('dob', {}).get('year', None)
            year = int(year)
        except ValueError:
            pass
        if year:
            age = 2017 - year
            if 13 < age < 101:
                ages.append(age)
    return dict(
        mean=statistics.mean(ages),
        median=statistics.median(ages),
        max=max(ages),
        min=min(ages))
