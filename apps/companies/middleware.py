class ActiveCompanyMiddleware:
    """
    Injects the authenticated user's active company into the request so
    downstream views can rely on server-managed tenant context.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and getattr(user, 'active_company_id', None):
            request.active_company = user.active_company
        return self.get_response(request)
