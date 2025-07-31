from .models import UserProfile

def generate_profile_id():
    profile_ids = [int(user.profile_id) for user in UserProfile.objects.exclude(profile_id__isnull=True).filter(is_active=True)]

    if not profile_ids:
        next_profile_id = "0001"
    else:
        max_profile_id = max(profile_ids)
        next_profile_id = str(max_profile_id + 1).zfill(4)

    return next_profile_id