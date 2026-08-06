from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    """
    Allows access only to Super Admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'userprofile') and 
            request.user.userprofile.role == 'SUPER_ADMIN'
        )


class IsBranchAdmin(permissions.BasePermission):
    """
    Allows access to Super Admins and Branch Admins.
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and hasattr(request.user, 'userprofile')):
            return False
        return request.user.userprofile.role in ['SUPER_ADMIN', 'BRANCH_ADMIN']


class IsBranchScoped(permissions.BasePermission):
    """
    Ensures users can only interact with data matching their assigned branch.
    """
    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated and hasattr(request.user, 'userprofile')):
            return False
            
        profile = request.user.userprofile
        if profile.role == 'SUPER_ADMIN':
            return True
            
        if hasattr(obj, 'branch'):
            return obj.branch == profile.branch
        return True