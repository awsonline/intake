from collections import namedtuple
from django.db import models
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from allauth.account.adapter import get_adapter
from allauth.account import utils as allauth_account_utils
from invitations.models import Invitation as BaseInvitation
from intake import models as intake_models
from intake import constants
from formation.forms import county_form_selector, display_form_selector
from . import exceptions


class NoEmailsForOrgError(Exception):
    pass


class UndefinedResourceAccessError(Exception):
    pass


class OrganizationManager(models.Manager):

    def get_by_natural_key(self, name):
        return self.get(name=name)


class Organization(models.Model):
    objects = OrganizationManager()
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, null=True)
    county = models.ForeignKey(intake_models.County,
                               on_delete=models.SET_NULL,
                               null=True, blank=True,
                               related_name='organizations')
    website = models.URLField(blank=True)
    blurb = models.TextField(blank=True)
    is_receiving_agency = models.BooleanField(default=False)
    requires_rap_sheet = models.BooleanField(default=False)
    requires_declaration_letter = models.BooleanField(default=False)
    show_pdf_only = models.BooleanField(default=False)
    new_submission_confirmation_message = models.TextField(blank=True)
    address = models.TextField(blank=True)
    phone_number = models.TextField(blank=True)
    email = models.TextField(blank=True)

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return (self.__str__(), )

    def get_transfer_org(self):
        """If this organization is allowed to transfer to another
        organization, this shoud return the other organization they are
        allowed to transfer submissions to.
        """
        if self.slug == constants.Organizations.ALAMEDA_PUBDEF:
            return self.__class__.objects.get(
                slug=constants.Organizations.EBCLC)
        elif self.slug == constants.Organizations.EBCLC:
            return self.__class__.objects.get(
                slug=constants.Organizations.ALAMEDA_PUBDEF)
        return None

    def get_referral_emails(self):
        """Get the emails of users who get notifications for this agency.
        This is not an efficient query and assumes that profiles and
        users have been prefetched in a previous query.
        """
        emails = [
            profile.user.email
            for profile
            in self.profiles.filter(should_get_notifications=True)]
        if not emails:
            # this assumes that any existing invitations are valid emails
            # to use for notification
            emails = list(Invitation.objects.filter(
                organization=self).values_list('email', flat=True))
        if not emails:
            msg = "{} has no invites or users".format(self)
            raise NoEmailsForOrgError(msg)
        return emails

    def has_a_pdf(self):
        """Checks for any linked intake.models.FillablePDF objects
        """
        return self.pdfs.count() > 0

    def get_default_form(self, display=False):
        """Get the basic input form for this organization
        For the time being, this is purely based on the county
        """
        form_selector = display_form_selector if display else county_form_selector
        return form_selector.get_combined_form_class(
            counties=[self.county.slug])

    def get_display_form(self):
        return self.get_default_form(display=True)

    def get_absolute_url(self):
        return reverse(
            'intake-partner_detail',
            kwargs=dict(organization_slug=self.slug))


class Address(models.Model):
    organization = models.ForeignKey(
                    'Organization',
                    on_delete=models.CASCADE,
                    related_name='addresses')
    name = models.TextField()
    text = models.TextField()
    walk_in_hours = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Addresses"

    def __str__(self):
        return self.text


class Invitation(BaseInvitation):
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE
    )

    @classmethod
    def create(cls, email, organization, inviter=None, **kwargs):
        key = get_random_string(64).lower()
        return cls._default_manager.create(
            email=email,
            organization=organization,
            key=key,
            inviter=inviter,
            **kwargs
        )

    def create_user_from_invite(self, password=None, accept=True, **kwargs):
        '''This is a utility function that
        creates a new user, with an associated profile and organization,
        from an existing invite.
        It should be used to programmatically create users, similar to
        django.contrib.auth.models.UserManager.create_user()
        If no password is supplied, this will assign an unusable password
        to the user.
        This method adapts steps from:
            allauth.account.forms.SignUpForm.save()
            allauth.account.forms.SignUpForm.save.adapter.save_user()
            user_accounts.forms.SignUpForm.custom_signup()
            allauth.account.utils.setup_user_email()
        This will mark the invite as accepted, or as designated in the
        `accept` option.
        '''
        if accept:
            self.accepted = True
            self.save()
        # get the right adapter
        allauth_adapter = get_adapter()
        MockRequest = namedtuple('MockRequest', 'session')
        mock_request = MockRequest(session={})
        # get an empty instance of designated U ser model
        user = allauth_adapter.new_user(request=mock_request)
        data = dict(email=self.email)
        if password:
            data['password1'] = password
        MockForm = namedtuple('MockForm', 'cleaned_data')
        user = allauth_adapter.save_user(
            request=mock_request,
            user=user,
            form=MockForm(cleaned_data=data)
        )
        UserProfile.create_from_invited_user(user, self, **kwargs)
        allauth_account_utils.setup_user_email(mock_request, user, [])
        return user


class UserProfile(models.Model):
    name = models.CharField(max_length=200, blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name='profile')
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.PROTECT,
        related_name='profiles'
    )
    should_get_notifications = models.BooleanField(default=False)

    def get_display_name(self):
        return self.name or self.user.email

    def __str__(self):
        return self.get_display_name()

    @classmethod
    def create_from_invited_user(cls, user, invitation=None, **kwargs):
        """
        This assumes we have a saved user and an
        accepted invite for that user's email
        """
        if not invitation:
            invitations = Invitation.objects.filter(
                email=user.email, accepted=True
            )
            invitation = invitations.first()
        if not invitation:
            raise exceptions.MissingInvitationError(
                "No invitation found for {}".format(user.email))
        profile = cls(
            user=user,
            organization=invitation.organization,
            **kwargs
        )
        profile.save()
        return profile

    def get_submission_display_form(self):
        """Returns a form class appropriate for displaying
        submission data to this user.
        For now, this is based on the default form for the organization
        """
        return self.organization.get_display_form()

    def should_see_pdf(self):
        """This should be based on whether or not this user's org has a pdf
        """
        return self.organization.has_a_pdf() or self.user.is_staff

    def should_have_access_to(self, resource):
        """Returns True if user is staff or shares one org with resource

        Raises an error for resources that don't have an `organization` or
        `organizations` attribute.
        """
        if self.user.is_staff:
            return True
        if hasattr(resource, 'organization'):
            return self.organization == resource.organization
        elif hasattr(resource, 'organizations'):
            return bool(resource.organizations.filter(
                pk=self.organization_id).count())
        msg = "`{}` doesn't have a way to define UserProfile access"
        raise UndefinedResourceAccessError(msg.format(resource))

    def filter_submissions(self, submissions_qset):
        if self.user.is_staff:
            return submissions_qset
        return submissions_qset.filter(organizations__profiles=self)


def get_user_display(user):
    return user.profile.get_display_name()
