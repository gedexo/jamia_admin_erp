from . import views
from django.urls import path


app_name = "masters"

urlpatterns = [
    # Request Submission
    path("request-submission/", views.RequestSubmissionListView.as_view(), name="request_submission_list"),
    path("my-request-submission/", views.MyRequestSubmissionListView.as_view(), name="my_request_submission_list"),
    path("shared-requests/", views.SharedRequestsListView.as_view(), name="shared_requests_list"),
    path("request-submission/<str:pk>/", views.RequestSubmissionDetailView.as_view(), name="request_submission_detail"),
    path("new/request-submission/", views.RequestSubmissionCreateView.as_view(), name="request_submission_create"),
    path("request-submission/<str:pk>/update/", views.RequestStatusUpdateView.as_view(), name="request_submission_update"),
    path("request-submission/<str:pk>/delete/", views.RequestSubmissionDeleteView.as_view(), name="request_submission_delete"),
    
    path("request-submission-pdf/<str:pk>/", views.download_request_submission_pdf, name="request_submission_pdf"),
    path("request-submission-pdf/<str:pk>/download/", views.RequestSubmissionPDFDownloadView.as_view(), name="request_submission_pdf_download"),

    # Request Submission Type
    path("request-submission-type/", views.RequestSubmissionTypeListView.as_view(), name="request_submission_type_list"),
    path("request-submission-type/<str:pk>/", views.RequestSubmissionTypeDetailView.as_view(), name="request_submission_type_detail"),
    path("new/request-submission-type/", views.RequestSubmissionTypeCreateView.as_view(), name="request_submission_type_create"),
    path("request-submission-type/<str:pk>/update/", views.RequestSubmissionTypeUpdateView.as_view(), name="request_submission_type_update"),
    path("request-submission-type/<str:pk>/delete/", views.RequestSubmissionTypeDeleteView.as_view(), name="request_submission_type_delete"),

    # Memo
    path("memos/", views.MemoListView.as_view(), name="memo_list"),
    path("memo/<str:pk>/", views.MemoDetailView.as_view(), name="memo_detail"),
    path("new/memo/", views.MemoCreateView.as_view(), name="memo_create"),
    path("memo/<str:pk>/update/", views.MemoUpdateView.as_view(), name="memo_update"),
    path("memo/<str:pk>/delete/", views.MemoDeleteView.as_view(), name="memo_delete"),
    
    # Autocomplete
    path("college-autocomplete/", views.CollegeAutocompleteView.as_view(), name="college_autocomplete"),
]
