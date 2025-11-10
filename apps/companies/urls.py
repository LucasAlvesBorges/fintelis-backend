from rest_framework.routers import DefaultRouter

from .views import CompanyViewSet, MembershipViewSet

router = DefaultRouter()
# Expose company endpoints directly under /api/v1/companies/
router.register('', CompanyViewSet, basename='companies')
router.register('memberships', MembershipViewSet, basename='memberships')

urlpatterns = router.urls
