from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter to handle user creation without a username field."""
    def populate_username(self, request, user):
        # Email-only user model — skip username generation.
        return

    def get_login_redirect_url(self, request):
        return reverse('courses:dashboard')

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        if not getattr(user, 'name', None):
            user.name = user.email.split('@')[0] if user.email else 'Trader'
        if commit:
            user.save()
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social adapter for Google OAuth integration with custom User model."""
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        # Extract name parts from Google profile data
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = (data.get('name') or '').strip()
        if not full_name and user.email:
            full_name = user.email.split('@')[0]
        user.name = full_name or 'Trader'
        return user

    def pre_social_login(self, request, sociallogin):
        """
        Safely link existing account if user already registered with the same email.
        Avoids creating duplicate accounts.
        """
        if sociallogin.is_existing:
            return

        if not sociallogin.email_addresses:
            return

        email = sociallogin.email_addresses[0].email
        if not email:
            return

        try:
            existing_user = User.objects.get(email__iexact=email)
            sociallogin.connect(request, existing_user)
        except User.DoesNotExist:
            pass
        except User.MultipleObjectsReturned:
            existing_user = User.objects.filter(email__iexact=email).order_by('id').first()
            if existing_user:
                sociallogin.connect(request, existing_user)
