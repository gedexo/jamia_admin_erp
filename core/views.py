import os
from django.templatetags.static import static
from core import mixins
from django.db.models import Q, F, Subquery, OuterRef, Exists, TextField
from django.db.models.functions import Cast
from django.db.models.fields import TextField
from django_tables2 import RequestConfig
from django.db.models import Count
from django.core.files.storage import default_storage
from core.pdfview import PDFView
from datetime import datetime, timedelta
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
from django.db.models.functions import Lower



class HomeView(mixins.HybridTemplateView):
    template_name = "core/dashboard.html"

    def get_user_profile_and_usertype(self, user):
        try:
            user_profile = UserProfile.objects.get(user=user)
            usertype = user_profile.user.usertype
        except UserProfile.DoesNotExist:
            user_profile = None
            usertype = getattr(user, 'usertype', None)
        return user_profile, usertype

    def get_status_counts(self, requests_queryset):
        user = self.request.user
        user_profile, usertype = self.get_user_profile_and_usertype(user)

        latest_status_subquery = RequestSubmissionStatusHistory.objects.filter(
            submission=OuterRef('pk')
        ).order_by('-date')

        requests_queryset = requests_queryset.annotate(
            latest_next_usertype=Subquery(latest_status_subquery.values('next_usertype')[:1]),
            latest_status=Lower(Subquery(latest_status_subquery.values('status')[:1]))
        )

        if usertype not in ["OE", "director"] and not user.is_superuser:
            requests_queryset = requests_queryset.filter(
                Q(latest_next_usertype=usertype) | Q(creator=user_profile.user)
            )

        approved = requests_queryset.filter(latest_status='approved').count()
        rejected = requests_queryset.filter(latest_status='rejected').count()
        processing = requests_queryset.filter(
            latest_status__in=['pending', 'processing'],
            latest_next_usertype=usertype
        ).count()
        pending = processing

        my_requests_count = requests_queryset.filter(creator=user_profile.user).count() if user_profile else 0

        return {
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
            'processing': processing,
            'my_requests': my_requests_count,
        }

    def get_pending_requests(self, user, user_profile):
        usertype = getattr(user, 'usertype', None)
        queryset = RequestSubmission.objects.filter(is_active=True).exclude(status__in=['approved', 'rejected'])

        if user_profile:
            latest_status_subquery = RequestSubmissionStatusHistory.objects.filter(
                submission=OuterRef('pk')
            ).order_by('-date')

            queryset = queryset.annotate(
                latest_next_usertype=Subquery(latest_status_subquery.values('next_usertype')[:1])
            )

            if usertype not in ["OE", "director"] and not user.is_superuser:
                queryset = queryset.filter(
                    Q(latest_next_usertype=usertype) | Q(creator=user_profile.user)
                )

            already_seen = RequestSubmissionStatusHistory.objects.filter(
                submission=OuterRef('pk'),
                usertype=usertype,
                submitted_users=user_profile
            )
            queryset = queryset.annotate(
                already_processed=Exists(already_seen)
            ).filter(already_processed=False)

            if user.is_superuser or usertype in ["director", "OE"]:
                return queryset
            else:
                return queryset.filter(creator=user_profile.user)
        else:
            return RequestSubmission.objects.none()

    def get_monthly_stats(self, queryset, date_field):
        months = []
        for i in range(6):
            date = timezone.now().date() - timedelta(days=30*i)
            month_start = date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            count = queryset.filter(**{
                f'{date_field}__gte': month_start,
                f'{date_field}__lte': month_end
            }).count()
            months.append({'month': month_start.strftime('%b %Y'), 'count': count})
        return list(reversed(months))

    def get_status_distribution(self, queryset):
        status_counts = {'on_hold': 0, 'approved': 0, 'rejected': 0}
        for request in queryset:
            latest_status = request.status_history.order_by('-date').first()
            if latest_status:
                status = latest_status.status
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts['on_hold'] += 1
            else:
                status_counts['on_hold'] += 1
        return [{'current_status': status, 'count': count} for status, count in status_counts.items() if count > 0]

    def get_usertype_distribution(self, queryset):
        if self.request.user.usertype in ["director", "OE"]:
            return queryset.exclude(is_superuser=True).values('usertype').annotate(
                count=Count('usertype')
            ).order_by('usertype')
        return queryset.values('usertype').annotate(count=Count('usertype')).order_by('usertype')

    def get_recent_status_changes(self, user):
        return RequestSubmissionStatusHistory.objects.filter(
            usertype="director",
            status__in=["approved", "rejected"]
        ).select_related('submission', 'user').order_by('-date')[:10]

    def get_avg_processing_time(self, queryset):
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
        total = queryset.count()
        if total == 0:
            return 0
        completed = sum(
            1 for request in queryset
            if request.status_history.order_by('-date').first() and
               request.status_history.order_by('-date').first().status in ['approved', 'rejected']
        )
        return round((completed / total) * 100, 1)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['is_dashboard'] = True

        user_profile, usertype = self.get_user_profile_and_usertype(user)
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_week = today - timedelta(days=today.weekday())

        base_queryset = RequestSubmission.objects.filter(is_active=True)
        users_qs = User.objects.filter(is_active=True)
        profiles_qs = UserProfile.objects.filter(is_active=True)

        if user.is_superuser:
            filtered_requests = base_queryset
        elif user_profile:
            if usertype == "College":
                # College users see their own requests (created by them)
                filtered_requests = base_queryset.filter(created_by=user_profile)
                
                # Status filter for college users
                status = self.request.GET.get("status", "").lower()
                if status in ["approved", "rejected", "pending"]:
                    filtered_requests = filtered_requests.filter(status=status)
            else:
                # Other users see requests assigned to them or submitted by them
                filtered_requests = base_queryset.filter(
                    Q(status_history__next_usertype=usertype) |
                    Q(status_history__submitted_users=user_profile)
                ).distinct().exclude(created_by=user_profile)
                
                # Status filter for non-college users
                status = self.request.GET.get("status", "").lower()
                if status in ["approved", "rejected"]:
                    oe_to_college_ids = RequestSubmissionStatusHistory.objects.filter(
                        usertype="OE",
                        next_usertype="College"
                    ).values_list('submission_id', flat=True)
                    filtered_requests = filtered_requests.filter(
                        id__in=oe_to_college_ids,
                        status=status
                    ).distinct()
                elif status == "processing":
                    filtered_requests = filtered_requests.filter(status="processing")
        else:
            filtered_requests = base_queryset.none()

        total_requests_count = filtered_requests.count()
        status_counts = self.get_status_counts(filtered_requests)

        if user.is_superuser:
            filtered_users = users_qs
            filtered_profiles = profiles_qs
        else:
            filtered_users = users_qs.filter(id=user.id)
            filtered_profiles = profiles_qs.filter(user=user)

        assigned_requests_count = 0
        if user_profile and not user.is_superuser:
            if usertype == "College":
                # For college users, assigned requests are their own requests
                assigned_requests_count = base_queryset.filter(
                    created_by=user_profile
                ).count()
            else:
                # For other users, assigned requests are those assigned to them
                latest_status_subquery = RequestSubmissionStatusHistory.objects.filter(
                    submission=OuterRef('pk')
                ).order_by('-date')
                assigned_requests_count = base_queryset.annotate(
                    latest_next_usertype=Subquery(latest_status_subquery.values('next_usertype')[:1])
                ).filter(
                    is_active=True,
                    latest_next_usertype=usertype
                ).exclude(
                    created_by=user_profile
                ).distinct().count()

        context.update({
            'total_users': UserProfile.objects.exclude(user__is_superuser=True, is_active=True).count(),
            'active_users': filtered_users.exclude(is_superuser=True).filter(is_active=True).count(),
            'new_users_this_month': UserProfile.objects.filter(
                user__is_active=True,
                user__date_joined__gte=start_of_month
            ).exclude(user__is_superuser=True).count(),
            'new_users_this_week': filtered_users.exclude(is_superuser=True).filter(date_joined__gte=start_of_week).count(),
            'total_profiles': filtered_profiles.count(),
            'profiles_with_photo': filtered_profiles.exclude(photo='').count(),
            'profiles_with_mobile': filtered_profiles.exclude(mobile='').count(),
            'total_requests': total_requests_count,
            'approved_requests': status_counts['approved'],
            'rejected_requests': status_counts['rejected'],
            'pending_requests': status_counts['pending'],
            'processing_requests': status_counts['processing'],
            'assigned_requests_count': assigned_requests_count,
            'my_requests_count': RequestSubmission.objects.filter(created_by=user_profile, is_active=True).count() if user_profile else 0,
            'my_pending_requests_count': RequestSubmission.objects.filter(created_by=user_profile, is_active=True, status__in=['pending', 'processing']).count() if user_profile else 0,
            'my_approved_requests_count': RequestSubmission.objects.filter(created_by=user_profile, is_active=True, status='approved').count() if user_profile else 0,
            'my_rejected_requests_count': RequestSubmission.objects.filter(created_by=user_profile, is_active=True, status='rejected').count() if user_profile else 0,
        })

        # Recent assigned requests logic
        recent_assigned_requests = []
        if user_profile and not user.is_superuser:
            if usertype == "College":
                assigned_qs = base_queryset.filter(created_by=user_profile)
            else:
                latest_status_subquery = RequestSubmissionStatusHistory.objects.filter(
                    submission=OuterRef('pk')
                ).order_by('-date')
                assigned_qs = base_queryset.annotate(
                    latest_next_usertype=Subquery(latest_status_subquery.values('next_usertype')[:1])
                ).filter(
                    is_active=True,
                    latest_next_usertype=usertype
                ).exclude(created_by=user_profile)
            
            assigned_qs = assigned_qs.distinct().order_by('-created')
            
            for req in assigned_qs[:10]:  # Limit to 10
                latest_assignment = req.status_history.filter(next_usertype=usertype).order_by('-date').first()
                if latest_assignment:
                    user_has_processed = req.status_history.filter(
                        submitted_users=user_profile,
                        usertype=usertype,
                        date__gt=latest_assignment.date
                    ).exists()
                else:
                    user_has_processed = False
                reassigned = req.status_history.filter(usertype=usertype).exclude(next_usertype=usertype).exists()
                req.dashboard_status = 'pending' if user_has_processed or reassigned else 'processing'
                req.is_created_by_user = (req.created_by_id == user_profile.id)
                recent_assigned_requests.append(req)

        re_assigned_requests_count = 0
        if user_profile and not user.is_superuser:
            director_reassign_qs = RequestSubmissionStatusHistory.objects.filter(
                submission__current_usertype=usertype,
                usertype="director",           
                status="re_assign",             
                next_usertype=usertype          
            ).values_list("submission_id", flat=True)

            re_assigned_requests_count = RequestSubmission.objects.filter(
                id__in=director_reassign_qs,
                is_active=True
            ).exclude(created_by=user_profile).distinct().count()

        context['recent_assigned_requests'] = recent_assigned_requests
        context["re_assigned_requests_count"] = re_assigned_requests_count
        pending_requests = filtered_requests.filter(status__in=['pending', 'processing'])
        context['pending_requests'] = pending_requests.count()
        context['recent_pending_requests'] = pending_requests.order_by('-created')[:5]

        # Other context data (charts, stats, etc.)
        context['monthly_request_stats'] = self.get_monthly_stats(filtered_requests, 'created')
        context['status_distribution'] = self.get_status_distribution(filtered_requests)
        context['usertype_distribution'] = self.get_usertype_distribution(filtered_users)
        context['recent_status_changes'] = self.get_recent_status_changes(user)
        context['avg_processing_time'] = self.get_avg_processing_time(filtered_requests)
        context['completion_rate'] = self.get_completion_rate(filtered_requests)

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
        """Get recent status changes: only director, only approved/rejected"""
        return RequestSubmissionStatusHistory.objects.filter(
            usertype="director",
            status__in=["approved", "rejected"]
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
    notifications = Notification.objects.filter(user=request.user, is_read=False, is_active=True).order_by('-created_at')[:99]
    def get_avatar_url():
        return static('app/assets/images/brand-logos/desktop-logo.png')
    data = [
        {
            'id': n.id,
            'message': n.message,
            'url': n.url,
            'is_read': n.is_read,
            'timestamp': n.created_at.isoformat(),
            'avatar_url': get_avatar_url(),
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

@login_required
@require_POST
def notification_clear_all(request):
    Notification.objects.filter(user=request.user, is_read=False, is_active=True).update(is_read=True)
    return JsonResponse({'success': True})
