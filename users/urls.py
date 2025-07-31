from . import views
from django.urls import path


app_name = "users"

urlpatterns = [
    path("user-profiles/", views.UserProfileListView.as_view(), name="user_profile_list"),
    path("college-users/", views.CollegeUserProfileListView.as_view(), name="college_user_profile_list"),
    path("user_profile/add/", views.UserProfileCreateView.as_view(), name="user_profile_create"),
    path("view/<pk>/", views.UserProfileDetailView.as_view(), name="user_profile_detail"),
    path("user_profile/change/<pk>/", views.UserProfileUpdateView.as_view(), name="user_profile_update"),
    path("user_profile/delete/<pk>/", views.UserProfileDeleteView.as_view(), name="user_profile_delete"),
]