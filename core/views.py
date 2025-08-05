import os
from core import mixins
from django.db.models import Q
from django_tables2 import RequestConfig
from django.db.models import Count
from django.core.files.storage import default_storage
from core.pdfview import PDFView
from datetime import datetime, timedelta
from django.db.models import Sum, Subquery, OuterRef
from django.conf import settings
from django.template import loader
from django.test import override_settings
from collections import defaultdict
from django.utils import timezone

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

# Import models
from accounts.models import User
from users.models import UserProfile
from masters.models import RequestSubmission, RequestSubmissionStatusHistory
from django.db import models
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from .models import Notification


class HomeView(mixins.HybridTemplateView):
    template_name = "core/dashboard.html"
    
    def get_status_counts(self, requests_queryset):
        """Return a dict with counts for approved, rejected, and pending based on the status field of RequestSubmission."""
        approved = requests_queryset.filter(status='approved').count()
        rejected = requests_queryset.filter(status='rejected').count()
        pending = requests_queryset.exclude(status__in=['approved', 'rejected']).count()
        return {'approved': approved, 'rejected': rejected, 'pending': pending}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dashboard'] = True

        # Always get user_profile at the start
        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get current date and calculate date ranges
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_week = today - timedelta(days=today.weekday())
        last_month = start_of_month - timedelta(days=1)
        last_month_start = last_month.replace(day=1)
        
        # Base querysets - exclude superusers for director dashboard
        if user.usertype == "director" or user.usertype == "OE":
            users_queryset = User.objects.filter(is_active=True, is_superuser=False)
            profiles_queryset = UserProfile.objects.filter(is_active=True)
            requests_queryset = RequestSubmission.objects.filter(is_active=True)
        else:
            users_queryset = User.objects.filter(is_active=True)
            profiles_queryset = UserProfile.objects.filter(is_active=True)
            requests_queryset = RequestSubmission.objects.filter(is_active=True)
        
        # Filter data based on user type
        if user.is_superuser or user.usertype == "director" or user.usertype == "OE":
            filtered_users = users_queryset
            filtered_profiles = profiles_queryset
            filtered_requests = requests_queryset
        else:
            filtered_users = users_queryset.filter(id=user.id)
            filtered_profiles = profiles_queryset.filter(user=user)
            
            if user.usertype == "College":
                # Only show requests created by the current College user
                filtered_requests = requests_queryset.filter(creator=user)
            else:
                filtered_requests = requests_queryset.filter(
                    Q(creator=user) |
                    Q(status_history__submitted_users=user_profile) |
                    Q(status_history__next_usertype=getattr(user, 'usertype', None))
                ).distinct()

        # User Statistics
        if user.usertype == "director" or user.usertype == "OE":
            context['total_users'] = filtered_users.exclude(is_superuser=True).count()
            context['active_users'] = filtered_users.exclude(is_superuser=True).filter(is_active=True).count()
            context['new_users_this_month'] = filtered_users.exclude(is_superuser=True).filter(date_joined__gte=start_of_month).count()
            context['new_users_this_week'] = filtered_users.exclude(is_superuser=True).filter(date_joined__gte=start_of_week).count()
        else:
            context['total_users'] = filtered_users.count()
            context['active_users'] = filtered_users.filter(is_active=True).count()
            context['new_users_this_month'] = filtered_users.filter(date_joined__gte=start_of_month).count()
            context['new_users_this_week'] = filtered_users.filter(date_joined__gte=start_of_week).count()
        
        # User Profile Statistics
        context['total_profiles'] = filtered_profiles.count()
        context['profiles_with_photo'] = filtered_profiles.exclude(photo='').count()
        context['profiles_with_mobile'] = filtered_profiles.exclude(mobile='').count()
        
        # Request Submission Statistics - using status field only
        context['total_requests'] = filtered_requests.count()
        status_counts = self.get_status_counts(filtered_requests)
        context['approved_requests'] = status_counts['approved']
        context['rejected_requests'] = status_counts['rejected']
        context['pending_requests'] = status_counts['pending']
        context['status_distribution'] = [
            {'current_status': 'approved', 'count': status_counts['approved']},
            {'current_status': 'rejected', 'count': status_counts['rejected']},
            {'current_status': 'pending', 'count': status_counts['pending']},
        ]
        # For college dashboard compatibility
        context['approved_count'] = status_counts['approved']
        context['rejected_count'] = status_counts['rejected']
        context['pending_count'] = status_counts['pending']

        # Recent Activity
        if user.usertype == "director" or user.usertype == "OE":
            director_requests = RequestSubmission.objects.all()
            director_recent_requests = []
            for req in director_requests.order_by('-created'):
                latest_status = req.status_history.order_by('-date').first()
                if latest_status and (latest_status.usertype == 'director' or latest_status.usertype == 'OE'):
                    director_recent_requests.append(req)
                if len(director_recent_requests) >= 5:
                    break
            context['recent_requests'] = director_recent_requests
        else:
            context['recent_requests'] = filtered_requests.order_by('-created')[:5]
        
        # Monthly Trends
        context['monthly_requests'] = self.get_monthly_stats(filtered_requests, 'created')
        if user.usertype == "director" or user.usertype == "OE":
            context['monthly_users'] = self.get_monthly_stats(filtered_users.exclude(is_superuser=True), 'date_joined')
        else:
            context['monthly_users'] = self.get_monthly_stats(filtered_users, 'date_joined')
        
        # User Type Distribution
        context['usertype_distribution'] = self.get_usertype_distribution(filtered_users)
        
        # Recent Status Changes
        context['recent_status_changes'] = self.get_recent_status_changes(user)
        
        # Performance Metrics
        context['avg_processing_time'] = self.get_avg_processing_time(filtered_requests)
        context['request_completion_rate'] = self.get_completion_rate(filtered_requests)
        
        # Assigned Requests for the logged-in user.
        if user_profile and not user.is_superuser:
            latest_status = RequestSubmissionStatusHistory.objects.filter(
                submission=OuterRef('pk')
            ).order_by('-date')
            assigned_requests = RequestSubmission.objects.annotate(
                latest_status_next_usertype=Subquery(latest_status.values('next_usertype')[:1]),
                latest_status_status=Subquery(latest_status.values('status')[:1]),
                latest_status_user_id=Subquery(latest_status.values('user_id')[:1])
            ).filter(
                latest_status_next_usertype=user.usertype
            ).exclude(
                Q(latest_status_status__in=['approved', 'rejected']) |
                Q(latest_status_user_id=user_profile.id)
            )
            
            # For College users, only show requests they created
            if user.usertype == "College":
                assigned_requests = assigned_requests.filter(creator=user)
        else:
            assigned_requests = RequestSubmission.objects.none()
        context['assigned_requests_count'] = assigned_requests.count()
        context['recent_assigned_requests'] = assigned_requests.order_by('-created')[:5]

        # Submitted Requests Count (replace pending_requests with submitted_requests) only for user dashboards
        if user_profile and user.usertype not in ["College", "director"] and not user.is_superuser:
            submitted_requests = RequestSubmission.objects.filter(
                status_history__submitted_users=user_profile
            ).distinct()
            context['submitted_requests'] = submitted_requests.count()
        else:
            context['submitted_requests'] = None

        # Add recent_users for profile summary in dashboard
        if user_profile:
            context['recent_users'] = [user_profile]
        else:
            context['recent_users'] = []

        return context
    
    def get_monthly_stats(self, queryset, date_field):
        """Get monthly statistics for the last 6 months"""
        months = []
        for i in range(6):
            date = timezone.now().date() - timedelta(days=30*i)
            month_start = date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            count = queryset.filter(**{
                f'{date_field}__gte': month_start,
                f'{date_field}__lte': month_end
            }).count()
            
            months.append({
                'month': month_start.strftime('%b %Y'),
                'count': count
            })
        
        return list(reversed(months))
    
    def get_status_distribution(self, queryset):
        """Get distribution of request statuses from latest status history"""
        status_counts = {'on_hold': 0, 'approved': 0, 'rejected': 0}
        
        for request in queryset:
            latest_status = request.status_history.order_by('-date').first()
            if latest_status:
                status = latest_status.status
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts['on_hold'] += 1  # Default to on_hold
            else:
                status_counts['on_hold'] += 1
        
        return [
            {'current_status': status, 'count': count}
            for status, count in status_counts.items()
            if count > 0
        ]
    
    def get_usertype_distribution(self, queryset):
        """Get distribution of user types"""
        if self.request.user.usertype == "director" or self.request.user.usertype == "OE":
            # For directors and OE, exclude superusers and show only regular user types
            return queryset.exclude(is_superuser=True).values('usertype').annotate(
                count=Count('usertype')
            ).order_by('usertype')
        else:
            return queryset.values('usertype').annotate(
                count=Count('usertype')
            ).order_by('usertype')
    
    def get_recent_status_changes(self, user):
        """Get recent status changes"""
        if user.is_superuser:
            return RequestSubmissionStatusHistory.objects.select_related(
                'submission', 'user'
            ).order_by('-date')[:10]
        elif user.usertype == "director" or user.usertype == "OE":
            # For directors and OE, exclude superuser-related status changes
            return RequestSubmissionStatusHistory.objects.exclude(
                user__user__is_superuser=True
            ).select_related('submission', 'user').order_by('-date')[:10]
        else:
            return RequestSubmissionStatusHistory.objects.filter(
                user__user=user
            ).select_related('submission', 'user').order_by('-date')[:10]
    
    def get_avg_processing_time(self, queryset):
        """Calculate average processing time for requests"""
        total_days = 0
        count = 0
        
        for request in queryset:
            status_history = request.status_history.order_by('date')
            if status_history.count() >= 2:
                first_status = status_history.first()
                last_status = status_history.last()
                
                if first_status and last_status:
                    days = (last_status.date - first_status.date).days
                    total_days += days
                    count += 1
        
        return round(total_days / count, 1) if count > 0 else 0
    
    def get_completion_rate(self, queryset):
        """Calculate request completion rate"""
        total = queryset.count()
        if total == 0:
            return 0
        
        completed = 0
        for request in queryset:
            latest_status = request.status_history.order_by('-date').first()
            if latest_status and latest_status.status in ['approved', 'rejected']:
                completed += 1
        
        return round((completed / total) * 100, 1)

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user, is_read=False, is_active=True).order_by('-created_at')[:10]
    def get_avatar_url(user):
        # Try to get user photo (student or employee), else fallback to default
        if hasattr(user, 'student') and getattr(user.student, 'photo', None):
            return user.student.photo.url
        elif hasattr(user, 'employee') and getattr(user.employee, 'photo', None):
            return user.employee.photo.url
        # fallback to a static default avatar
        from django.templatetags.static import static
        return static('app/assets/images/brand-logos/desktop-logo.png')
    data = [
        {
            'id': n.id,
            'message': n.message,
            'url': n.url,
            'is_read': n.is_read,
            'timestamp': n.created_at.isoformat(),
            'avatar_url': get_avatar_url(n.user),
        } for n in notifications
    ]
    return JsonResponse({'notifications': data, 'count': notifications.count()})

@login_required
def notification_read_and_redirect(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user, is_active=True)
    notification.is_read = True
    notification.save()
    return HttpResponseRedirect(notification.url)

@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user, is_active=True)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True, 'url': notification.url})
