import secrets
import urllib.parse
import requests
from django.conf import settings
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .forms import SignUpForm, SignInForm, UserProfileForm, CustomPasswordChangeForm


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('courses:dashboard')

    next_url = request.GET.get('next') or request.POST.get('next')
    plan = request.GET.get('plan') or request.POST.get('plan')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='accounts.backends.EmailAuthBackend')
            messages.success(request, f"Welcome to Tradex Academy, {user.name}! Your account has been created.")
            
            if plan:
                return redirect(f"/subscriptions/checkout/?plan={plan}")
            if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('courses:dashboard')
        else:
            messages.error(request, "Please correct the errors below to complete your registration.")
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {
        'form': form,
        'next': next_url,
        'plan': plan,
    })


def signin_view(request):
    if request.user.is_authenticated:
        return redirect('courses:dashboard')

    next_url = request.GET.get('next') or request.POST.get('next')
    plan = request.GET.get('plan') or request.POST.get('plan')

    if request.method == 'POST':
        form = SignInForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.name}!")
                    if plan:
                        return redirect(f"/subscriptions/checkout/?plan={plan}")
                    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect('courses:dashboard')
                else:
                    messages.error(request, "Your account has been deactivated. Please contact support.")
            else:
                messages.error(request, "Invalid email or password. Please try again.")
        else:
            messages.error(request, "Please enter a valid email and password.")
    else:
        form = SignInForm()

    return render(request, 'accounts/signin.html', {
        'form': form,
        'next': next_url,
        'plan': plan,
    })


@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('accounts:signin')


@login_required
def profile_view(request):
    """Account profile view to edit personal details and change password."""
    profile_form = UserProfileForm(instance=request.user)
    password_form = CustomPasswordChangeForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            profile_form = UserProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Account profile details have been updated.")
                return redirect('accounts:profile')
            else:
                messages.error(request, "Please correct the errors in the profile form.")
                
        elif action == 'change_password':
            password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password has been changed successfully.")
                return redirect('accounts:profile')
            else:
                messages.error(request, "Please check the password requirements and try again.")

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'user': request.user,
        'has_subscription': request.user.has_active_subscription,
        'active_subscription': request.user.active_subscription,
    })


def google_login_view(request):
    """Initiates Google OAuth 2.0 authorization code flow."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        return redirect('courses:dashboard')

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
    if not client_id:
        messages.error(
            request,
            "Google sign-in is not yet configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your settings."
        )
        return redirect('accounts:signin')

    # Generate secure random state token to protect against CSRF
    state = secrets.token_urlsafe(32)
    request.session['google_oauth_state'] = state

    # Capture 'next' and 'plan' parameters
    next_url = request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
        request.session['google_oauth_next'] = next_url

    plan = request.GET.get('plan')
    if plan:
        request.session['google_oauth_plan'] = plan

    # Determine redirect URI (allow settings override or auto-detect from request)
    override_redirect = getattr(settings, 'GOOGLE_REDIRECT_URI', '').strip()
    if override_redirect:
        redirect_uri = override_redirect
    else:
        redirect_uri = request.build_absolute_uri(reverse('accounts:google_callback'))
        # Fix protocol on Vercel or when behind SSL proxy
        if (getattr(settings, 'IS_VERCEL', False) or request.is_secure()) and redirect_uri.startswith('http://'):
            redirect_uri = 'https://' + redirect_uri[7:]

    request.session['google_oauth_redirect_uri'] = redirect_uri
    request.session.modified = True

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)


def google_callback_view(request):
    """Handles callback from Google OAuth 2.0."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        return redirect('courses:dashboard')

    # Check if Google returned an error
    error = request.GET.get('error')
    if error:
        messages.error(request, f"Google authentication was cancelled or encountered an error: {error}")
        return redirect('accounts:signin')

    code = request.GET.get('code')
    state = request.GET.get('state')
    saved_state = request.session.pop('google_oauth_state', None)

    if not state or not saved_state or state != saved_state:
        messages.error(request, "Google sign-in session expired or security verification failed. Please try again.")
        return redirect('accounts:signin')

    if not code:
        messages.error(request, "No authorization code returned from Google. Please try again.")
        return redirect('accounts:signin')

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '').strip()
    saved_redirect = request.session.pop('google_oauth_redirect_uri', None)
    redirect_uri = saved_redirect or getattr(settings, 'GOOGLE_REDIRECT_URI', '').strip() or request.build_absolute_uri(reverse('accounts:google_callback'))
    if (getattr(settings, 'IS_VERCEL', False) or request.is_secure()) and redirect_uri.startswith('http://'):
        redirect_uri = 'https://' + redirect_uri[7:]

    # Exchange authorization code for tokens
    token_payload = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }

    try:
        token_resp = requests.post(
            'https://oauth2.googleapis.com/token',
            data=token_payload,
            headers={'Accept': 'application/json'},
            timeout=10,
        )
        token_data = token_resp.json()
    except Exception as exc:
        messages.error(request, f"Unable to reach Google authentication service: {exc}")
        return redirect('accounts:signin')

    if token_resp.status_code != 200 or 'access_token' not in token_data:
        err_msg = token_data.get('error_description') or token_data.get('error') or 'Token exchange failed'
        messages.error(request, f"Google authorization failed: {err_msg}")
        return redirect('accounts:signin')

    # Fetch user profile from Google UserInfo endpoint
    access_token = token_data['access_token']
    try:
        userinfo_resp = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        userinfo = userinfo_resp.json()
    except Exception as exc:
        messages.error(request, f"Unable to retrieve Google user profile: {exc}")
        return redirect('accounts:signin')

    if userinfo_resp.status_code != 200 or not userinfo.get('email'):
        messages.error(request, "Could not retrieve email address from your Google account.")
        return redirect('accounts:signin')

    email = userinfo['email'].strip().lower()
    email_verified = userinfo.get('email_verified', False)
    name = (userinfo.get('name') or userinfo.get('given_name') or email.split('@')[0]).strip()

    if not email_verified:
        messages.error(request, "Your Google email address has not been verified by Google. Please verify it first.")
        return redirect('accounts:signin')

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    is_new = False

    if not user:
        # Create a new user with verified Google details
        user = User.objects.create_user(
            email=email,
            name=name or 'Trader',
            password=None,
        )
        user.set_unusable_password()
        user.save()
        is_new = True
    else:
        # If user name was empty, update with Google name
        if not user.name and name:
            user.name = name
            user.save(update_fields=['name'])

    if not user.is_active:
        messages.error(request, "Your account has been deactivated. Please contact support.")
        return redirect('accounts:signin')

    # Authenticate user session
    login(request, user, backend='accounts.backends.EmailAuthBackend')

    if is_new:
        messages.success(request, f"Welcome to Tradex Academy, {user.name}! Your account was created with Google.")
    else:
        messages.success(request, f"Welcome back, {user.name}!")

    plan = request.session.pop('google_oauth_plan', None)
    next_url = request.session.pop('google_oauth_next', None)
    if plan:
        return redirect(f"/subscriptions/checkout/?plan={plan}")
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('courses:dashboard')
