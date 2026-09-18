from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .forms import SignUpForm, SignInForm, UserProfileForm, CustomPasswordChangeForm


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('courses:dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='accounts.backends.EmailAuthBackend')
            messages.success(request, f"Welcome to the Trading Academy, {user.name}! Your account has been created.")
            return redirect('courses:dashboard')
        else:
            messages.error(request, "Please correct the errors below to complete your registration.")
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


def signin_view(request):
    if request.user.is_authenticated:
        return redirect('courses:dashboard')

    next_url = request.GET.get('next', 'courses:dashboard')

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
                    return redirect(request.POST.get('next') or next_url)
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
        'next': next_url
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
