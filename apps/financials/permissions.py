from rest_framework import permissions


class IsCompanyMember(permissions.BasePermission):
    """
    Ensures requests include an active company and that the user belongs to it.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # get_active_company raises ValidationError or PermissionDenied with useful messages.
        view.get_active_company()
        return True
