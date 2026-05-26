def user_profile(request):
    """Inject `profile` into template context for authenticated users.

    Returns None when no profile exists or user is anonymous.
    """
    profile = None
    try:
        if request.user.is_authenticated:
            profile = getattr(request.user, 'userprofile', None)
    except Exception:
        profile = None
    return {'profile': profile}
