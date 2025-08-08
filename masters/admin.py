from django.contrib import admin
from .models import Memo, RequestSubmission, RequestSubmissionStatusHistory, RequestSubmissionType

@admin.register(RequestSubmissionType)
class RequestSubmissionTypeAdmin(admin.ModelAdmin):
    list_display = ['title',]

@admin.register(RequestSubmission)
class RequestSubmissionAdmin(admin.ModelAdmin):
    list_display = ['title', 'current_usertype', 'created_by']
    list_filter = ['current_usertype', 'created_by', 'status', 'is_active']
    search_fields = ['title', 'description']

@admin.register(RequestSubmissionStatusHistory)
class RequestSubmissionStatusHistoryAdmin(admin.ModelAdmin):
    list_display  = ['submission', 'usertype', 'status', 'date']  
    list_filter   = ['status', 'usertype']
    search_fields = ['submission__title', 'user__username']
    raw_id_fields = ['submission']
    date_hierarchy = 'date'
    ordering      = ['-date']
    list_per_page = 20

@admin.register(Memo)
class MemoAdmin(admin.ModelAdmin):
    list_display = ['title',]
    list_filter = ['college']
    search_fields = ['title', 'description']
    raw_id_fields = ['college']
    date_hierarchy = 'created'
    ordering      = ['-created']
    list_per_page = 20