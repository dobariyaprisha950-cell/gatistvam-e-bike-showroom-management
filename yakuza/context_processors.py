from django.db.models import Q
from .models import Notification, UserProfile, Branch

def notification_context(request):
    if request.user.is_authenticated:
        user = request.user
        profile = getattr(user, 'userprofile', None)

        if (user.is_superuser) or (profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN):
            unread_count = Notification.objects.filter(is_read=False).count()
        elif profile and profile.branch:
            unread_count = Notification.objects.filter(
                Q(branch=profile.branch) | Q(branch__isnull=True),
                is_read=False
            ).count()
        else:
            unread_count = 0

        return {'unread_notifications_count': unread_count}
        
    return {'unread_notifications_count': 0}


def branch_context_processor(request):
    if request.user.is_authenticated:
        user = request.user
        profile = getattr(user, 'userprofile', None)
        if user.is_superuser or (profile and profile.role == UserProfile.RoleChoices.SUPER_ADMIN):
            return {
                'all_active_branches': Branch.objects.filter(is_active=True)
            }
    return {}