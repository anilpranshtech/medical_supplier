# context_processors.py
from utils.handle_user_profile import get_user_profile


def header_avatar(request):
    if request.user.is_authenticated:
        profile, _ = get_user_profile(request.user)
        if profile and profile.profile_picture:
            return {
                'header_avatar_url': profile.profile_picture.url
            }
    return {
        'header_avatar_url': None
    }