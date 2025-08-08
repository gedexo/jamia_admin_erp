import sys
from django.template.loader import render_to_string
from django.forms import MultipleChoiceField, MultipleHiddenInput
from django import forms
from weasyprint import HTML, CSS
from django.templatetags.static import static
from django.contrib.auth import get_user_model
from .models import Memo, RequestSubmission, RequestSubmissionStatusHistory, RequestSubmissionType
from .forms import RequestStatusUpdateForm, RequestSubmissionTypeForm
from django.urls import reverse_lazy
from django.shortcuts import redirect
from core import mixins
from . import tables
from . import forms
from django.db.models import OuterRef, Exists, Subquery, Max, Q
from django.db import transaction
from django.shortcuts import get_object_or_404
from core.choices import USERTYPE_CHOICES, REQUEST_SUBMISSION_STATUS_CHOICES

from reportlab.pdfgen import canvas
from core.pdfview import PDFView
from django.utils import timezone
from django.http import HttpResponse
from weasyprint import HTML
from core.models import Notification
from users.models import UserProfile
from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.db.models import ForeignKey, OneToOneField, ManyToManyField
from django.views.generic import View
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse
from django_filters import FilterSet, CharFilter, ChoiceFilter


class RequestSubmissionListView(mixins.HybridListView):
    model = RequestSubmission
    table_class = tables.RequestSubmissionTable
    filterset_fields = {"title": ["exact"], "college": ["exact"], "status":['exact']}
    permissions = ()

    def get_queryset(self):
        user = self.request.user

        # Superuser can see all
        if user.is_superuser:
            return RequestSubmission.objects.all()

        qs = super().get_queryset()

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return qs.none()

        usertype = user_profile.user.usertype

        # Annotate processing status
        already_processed = RequestSubmissionStatusHistory.objects.filter(
            submission=OuterRef('pk'),
            usertype=usertype,
            submitted_users=user_profile
        )
        qs = qs.annotate(
            is_processing=~Exists(already_processed)
        )

        # Exclude requests created by logged-in user
        qs = qs.exclude(created_by=user_profile)

        if usertype == "College":
            # Show requests NOT created by this college user, excluding processing
            qs = qs.exclude(status="processing")

            # Filter by status if provided (approved, rejected, pending)
            status = self.request.GET.get("status", "").lower()
            if status in ["approved", "rejected", "pending"]:
                qs = qs.filter(status=status)

        else:
            # Other users see requests assigned to or submitted by them, excluding their own created
            qs = qs.filter(
                Q(status_history__next_usertype=usertype) |
                Q(status_history__submitted_users=user_profile)
            ).distinct()

            # Status filter for non-college
            status = self.request.GET.get("status", "").lower()
            if status in ["approved", "rejected"]:
                oe_to_college_ids = RequestSubmissionStatusHistory.objects.filter(
                    usertype="OE",
                    next_usertype="College"
                ).values_list('submission_id', flat=True)

                qs = qs.filter(
                    id__in=oe_to_college_ids,
                    status=status
                ).distinct()

            elif status == "processing":
                qs = qs.filter(status="processing")

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "is_master": True,
            "is_request_submission": True,
            "can_add": False,
            "new_link": reverse_lazy("masters:request_submission_create")
        })
        return context


class MyRequestSubmissionListView(mixins.HybridListView):
    model = RequestSubmission
    table_class = tables.MyRequestSubmissionTable
    filterset_fields = {"title": ["exact"], "college": ["exact"], "status": ['exact']}
    permissions = ()

    def get_queryset(self):
        user = self.request.user
        usertype = user.usertype

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return RequestSubmission.objects.none()

        qs = RequestSubmission.objects.filter(created_by=user_profile)

        return qs.annotate(
            oe_assigned_to_me=Exists(
                RequestSubmissionStatusHistory.objects.filter(
                    submission=OuterRef("pk"),
                    usertype="OE",
                    next_usertype=usertype
                )
            ),
            submitted_by_me=Exists(
                RequestSubmissionStatusHistory.objects.filter(
                    submission=OuterRef("pk"),
                    submitted_users=user_profile
                )
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "is_master": True,
            "is_my_request_submission": True,
            "can_add": False,
            "new_link": reverse_lazy("masters:request_submission_create")
        })
        return context


class RequestSubmissionDetailView(mixins.HybridDetailView):
    template_name = "masters/request_submission/request_submission_detail.html"
    model = RequestSubmission
    permissions = ()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_delete"] = mixins.check_access(self.request, ("is_superuser", "director"))

        latest_status = self.object.status_history.first()
        context["latest_next_usertype"] = latest_status.next_usertype if latest_status else None
        context["latest_status"] = latest_status

        try:
            user_profile = UserProfile.objects.get(user=self.request.user)
        except UserProfile.DoesNotExist:
            user_profile = None

        is_college_user_of_creator = (
            self.request.user.usertype == "College"
            and self.object.college == user_profile.college
        )
        context["is_college_user_of_creator"] = is_college_user_of_creator

        if user_profile and (user_profile.user.usertype == "director" or self.request.user.is_superuser):
            context["status_history"] = self.object.status_history.all()
        elif user_profile:
            usertype = user_profile.user.usertype
            director_assigned = self.object.status_history.filter(
                user__user__usertype="director",
                next_usertype=usertype
            )
            self_submitted = self.object.status_history.filter(
                user=user_profile
            )
            context["status_history"] = (director_assigned | self_submitted).distinct().order_by("-date")
        else:
            context["status_history"] = []

        context["latest_submitted_user_ids"] = (
            list(latest_status.submitted_users.values_list('user__id', flat=True))
            if latest_status else []
        )

        return context


class RequestSubmissionCreateView(mixins.HybridCreateView):
    model = RequestSubmission
    template_name = "masters/request_submission/request_submission_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "New Request Submission"
        context["is_request_submission_form"] = True
        context['current_usertype'] = self.request.user.usertype
        
        if self.request.user.usertype == "OE":
            usertype_choices = list(USERTYPE_CHOICES)
            excluded_usertypes = ['College', 'OE', 'director']
            context['available_flow_usertypes'] = [
                (value, label) for value, label in usertype_choices 
                if value not in excluded_usertypes
            ]
            # Initialize usertype_flow in form
            if 'form' not in context or context['form'] is None:
                context['form'] = self.get_form()
            context['form'].fields['usertype_flow'].initial = []
        
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user_usertype = self.request.user.usertype
        allowed_fields = ['title', 'description', 'attachment']

        if user_usertype == "OE":
            # Add usertype_flow field for OE users
            form.fields['usertype_flow'] = MultipleChoiceField(
                choices=[(v, l) for v, l in USERTYPE_CHOICES if v not in ['College', 'OE', 'director']],
                required=False,
                widget=MultipleHiddenInput()
            )
            allowed_fields.append('usertype_flow')

        # Remove fields not in allowed_fields
        for field_name in list(form.fields):
            if field_name not in allowed_fields:
                del form.fields[field_name]

        return form

    @transaction.atomic
    def form_valid(self, form):
        user_profile = UserProfile.objects.get(user=self.request.user)
        form.instance.college = user_profile
        form.instance.current_usertype = user_profile.user.usertype
        form.instance.created_by = user_profile

        if user_profile.user.usertype == "OE":
            # Get the selected usertypes from form data
            selected_usertypes = self.request.POST.getlist('usertype_flow', [])
            
            # Build the full flow: OE -> selected usertypes -> director
            full_flow = ["OE"]
            if selected_usertypes:
                full_flow.extend(selected_usertypes)
            full_flow.append("director")
            
            form.instance.usertype_flow = full_flow
            form.instance.status = "pending"
            
            # Set next usertype in flow
            if len(full_flow) > 1:
                form.instance.current_usertype = full_flow[1]
        else:
            # For other usertypes (e.g. College), keep existing fixed flow
            form.instance.usertype_flow = [user_profile.user.usertype, "OE"]
            form.instance.status = "pending"
            form.instance.current_usertype = "OE"

        response = super().form_valid(form)

        # Create initial status history
        next_usertype = form.instance.usertype_flow[1] if len(form.instance.usertype_flow) > 1 else ""
        RequestSubmissionStatusHistory.objects.create(
            submission=form.instance,
            user=user_profile,
            usertype=user_profile.user.usertype,
            next_usertype=next_usertype,
            status='pending',
            remark=f"{user_profile.user.usertype} created the request."
        )

        # Send notifications if needed
        if form.instance.current_usertype:
            next_profiles = UserProfile.objects.filter(user__usertype=form.instance.current_usertype)
            for profile in next_profiles:
                notification = Notification(
                    user=profile.user,
                    message=f"New request assigned: {form.instance.title}",
                    url=form.instance.get_absolute_url()
                )
                notification._request = self.request
                notification.save()

        return response

    def get_success_url(self):
        return reverse_lazy('masters:my_request_submission_list')
    

class RequestStatusUpdateView(mixins.HybridUpdateView):
    model = RequestSubmission
    form_class = RequestStatusUpdateForm
    template_name = "masters/request_submission/request_submission_form.html"

    def get_next_usertype(self, submission, current_usertype):
        flow = submission.usertype_flow or []
        try:
            current_index = flow.index(current_usertype)
            if current_index > 0 and flow[current_index - 1] == "director":
                return "director"
            elif current_index + 1 < len(flow):
                return flow[current_index + 1]
            else:
                return None
        except ValueError:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usertype_choices'] = USERTYPE_CHOICES
        if self.request.user.usertype == 'director' and hasattr(self.object, 'usertype_flow'):
            usertype_labels = dict(USERTYPE_CHOICES)
            flow = self.object.usertype_flow or []
            reassign_choices = [
                (key, usertype_labels.get(key, key))
                for key in flow
                if key != 'director'
            ]
            context['reassign_usertype_choices'] = reassign_choices
        context['next_usertype'] = self.get_next_usertype(self.object, self.request.user.usertype)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user_profile = UserProfile.objects.get(user=self.request.user)
        kwargs.update({
            "usertype": user_profile.user.usertype,
        })
        return kwargs

    def form_valid(self, form):
        user_profile = UserProfile.objects.get(user=self.request.user)
        submission = form.instance
        current_usertype = user_profile.user.usertype
        reassign_to = self.request.POST.get("reassign_usertype")
        remark = form.cleaned_data.get("remark")

        if current_usertype == "director":
            if reassign_to:
                flow = submission.usertype_flow or []
                if flow and flow[-1] == "director":
                    if reassign_to not in flow:
                        flow.insert(-1, reassign_to)
                else:
                    if reassign_to not in flow:
                        flow.append(reassign_to)
                submission.usertype_flow = flow
                submission.current_usertype = reassign_to
            else:
                submission.current_usertype = "OE"
                flow = submission.usertype_flow or []
                if "OE" not in flow:
                    flow.append("OE")
                if "director" not in flow:
                    flow.append("director")
                submission.usertype_flow = flow

        elif current_usertype == "OE":
            if submission.status_history.filter(usertype="OE").count() == 0:
                remark = remark or "Created usertype flow"

            user_flow = form.cleaned_data.get("user_flow", [])
            user_flow = [ut for ut in user_flow if ut not in ("College", "OE", "director")]

            current_flow = submission.usertype_flow or []

            if current_flow and current_flow[-1] == "director":
                current_flow = current_flow[:-1]

            for ut in user_flow:
                if ut not in current_flow:
                    current_flow.append(ut)

            current_flow.append("director")
            submission.usertype_flow = current_flow

            submitted_usertypes = list(submission.status_history.values_list("usertype", flat=True))

            next_usertype = None
            try:
                current_index = submission.usertype_flow.index(current_usertype)
                for candidate in submission.usertype_flow[current_index + 1:]:
                    if candidate not in submitted_usertypes:
                        next_usertype = candidate
                        break
            except ValueError:
                next_usertype = None

            submission.current_usertype = next_usertype

        else:
            flow = submission.usertype_flow or []
            last_index = len(flow) - 2 if len(flow) >= 2 and flow[-1] == "director" else len(flow) - 1
            try:
                if last_index >= 0 and flow[last_index] == current_usertype and flow[last_index + 1] == "director":
                    submission.current_usertype = "director"
                else:
                    current_index = flow.index(current_usertype)
                    if current_index > 0 and flow[current_index - 1] == "director":
                        submission.current_usertype = "director"
                    elif current_index + 1 < len(flow) and flow[current_index + 1] == "director":
                        submission.current_usertype = "director"
                    elif current_index + 1 < len(flow):
                        submission.current_usertype = flow[current_index + 1]
                    else:
                        submission.current_usertype = None
            except ValueError:
                submission.current_usertype = "director"

        submission.updated_by = user_profile
        submission.save()

        history_record = RequestSubmissionStatusHistory.objects.create(
            submission=submission,
            user=user_profile,
            usertype=current_usertype,
            status=form.cleaned_data.get("status", "forwarded"),
            remark=remark,
            next_usertype=submission.current_usertype or "",
        )
        history_record.submitted_users.add(user_profile)

        if submission.current_usertype == "College":
            if submission.created_by and submission.created_by.user:
                notification = Notification(
                    user=submission.created_by.user,
                    message=f"Your request '{submission.title}' has been sent to College.",
                    url=submission.get_absolute_url()
                )
                notification._request = self.request
                notification.save()
        elif submission.current_usertype:
            next_profiles = UserProfile.objects.filter(user__usertype=submission.current_usertype)
            for profile in next_profiles:
                notification = Notification(
                    user=profile.user,
                    message=f"Request assigned: {submission.title}",
                    url=submission.get_absolute_url()
                )
                notification._request = self.request
                notification.save()

        if submission.current_usertype is None:
            if submission.created_by and submission.created_by.user:
                notification = Notification(
                    user=submission.created_by.user,
                    message=f"Your request '{submission.title}' has been fully submitted and processed.",
                    url=submission.get_absolute_url()
                )
                notification._request = self.request
                notification.save()

        return redirect(submission.get_absolute_url())

    def form_invalid(self, form):
        print("Form errors:", form.errors, file=sys.stdout)
        return super().form_invalid(form)


class RequestSubmissionDeleteView(mixins.HybridDeleteView):
    model = RequestSubmission
    permissions = ("director", "is_superuser")

def download_request_submission_pdf(request, pk):
    instance = get_object_or_404(RequestSubmission, pk=pk)

    # Determine which remark to show based on current usertype
    if request.user.usertype == "OE":
        # Get latest director remark
        last_remark = (
            instance.status_history
            .filter(usertype="director", remark__isnull=False)
            .order_by("-date")
            .first()
        )
    else:
        # Get latest OE remark (or fallback as needed)
        last_remark = (
            instance.status_history
            .filter(usertype="OE", remark__isnull=False)
            .order_by("-date")
            .first()
        )

    full_text = last_remark.remark if last_remark else ""

    # Word splitting for pages
    first_page_length = 370
    other_page_length = 423

    words = full_text.split()
    chunks = []
    if len(words) > first_page_length:
        chunks.append(' '.join(words[:first_page_length]))
        for i in range(first_page_length, len(words), other_page_length):
            chunks.append(' '.join(words[i:i + other_page_length]))
    else:
        chunks.append(' '.join(words))

    context = {
        "instance": instance,
        "chunks": chunks,
        "request": request,
    }

    html_string = render_to_string(
        'masters/request_submission/pdf/request_submission_pdf.html',
        context
    )
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))

    pdf_file = html.write_pdf(stylesheets=[
        CSS(string='''
            @page {
                size: A4;
                margin: 0mm;
            }
        ''')
    ])

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="request_submission.pdf"'
    return response


class RequestSubmissionPDFDownloadView(PDFView):
    template_name = 'masters/request_submission/pdf/request_submission_download_pdf.html'
    pdfkit_options = {
        "page-width": 210,
        "page-height": 297,
        "encoding": "UTF-8",
        "margin-top": "0",
        "margin-bottom": "0",
        "margin-left": "0",
        "margin-right": "0",
        "enable-smart-shrinking": "",
        "zoom": 0.8,
        "minimum-font-size": 8,
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = get_object_or_404(RequestSubmission, pk=self.kwargs["pk"])
        context["title"] = "Request Submission"
        context["instance"] = instance

        director_remark = (
            instance.status_history
            .filter(usertype="director", remark__isnull=False)
            .order_by("-date")
            .first()
        )

        context["director_remark"] = director_remark.remark if director_remark else ""
        return context
    
    def get_filename(self):
        return "request_submissions.pdf"

    
class RequestSubmissionTypeListView(mixins.HybridListView):
    model = RequestSubmissionType
    table_class = tables.RequestSubmissionTypeTable
    filterset_fields = {"title": ["exact"],}
    permissions = ("is_superuser", "director", "OE")

    def get_queryset(self):
        return RequestSubmissionType.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Request Submission Type"
        context["new_link"] = reverse_lazy("masters:request_submission_type_create")
        context["can_add"] = True
        context["is_master"] = True
        context["is_request_submission_type"] = True
        return context

    
class RequestSubmissionTypeDetailView(mixins.HybridDetailView):
    model = RequestSubmissionType
    permissions = ("is_superuser", "director", "OE")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Request Submission Type"
        return context

    
class RequestSubmissionTypeCreateView(mixins.HybridCreateView):
    model = RequestSubmissionType
    permissions = ("is_superuser", "director", "OE")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "New Request Submission Type"
        return context

    def get_success_url(self):
        return reverse_lazy("masters:request_submission_type_list")

    
class RequestSubmissionTypeUpdateView(mixins.HybridUpdateView):
    model = RequestSubmissionType
    permissions = ("is_superuser", "director", "OE")
    form_class = RequestSubmissionTypeForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Update Request Submission Type"
        return context

    def get_success_url(self):
        return reverse_lazy("masters:request_submission_type_list")

    
class RequestSubmissionTypeDeleteView(mixins.HybridDeleteView):
    model = RequestSubmissionType
    permissions = ("is_superuser", "director", "OE")
    
    

class MemoListView(mixins.HybridListView):
    model = Memo
    table_class = tables.MemoTable
    filterset_fields = {"title": ["exact"],}
    permissions = ("is_superuser", "director", "OE", "College")

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return Memo.objects.filter(is_active=True)

        elif user.usertype == "College":
            try:
                user_profile = UserProfile.objects.get(user=user)
                return Memo.objects.filter(college=user_profile, is_active=True)
            except UserProfile.DoesNotExist:
                return Memo.objects.none()

        return Memo.objects.filter(is_active=True)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["title"] = "Memo List"
        context["is_master"] = True
        context["is_memo"] = True
        context["can_add"] = user.usertype in ["director", "OE"]
        return context
    

class MemoDetailView(mixins.HybridDetailView):
    model = Memo
    permissions = ("is_superuser", "director", "OE", "College")
    template_name = "masters/memo/memo_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Memo"
        return context
    
    
class MemoCreateView(mixins.HybridCreateView):
    model = Memo
    exclude = ['is_active']
    permissions = ("is_superuser", "director", "OE")
    form_class = forms.MemoForm
    template_name = "masters/memo/memo_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['college'].queryset = UserProfile.objects.filter(user__usertype='College', is_active=True)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_master"] = True
        context["is_memo"] = True
        return context

    def form_valid(self, form):

        try:
            response = super().form_valid(form)
            memo = self.object

            select_all = self.request.POST.get('select_all', 'no')
            if select_all == "yes":
                selected_colleges = UserProfile.objects.filter(user__usertype='College', is_active=True)
            else:
                selected_colleges = form.cleaned_data.get('college', [])

            memo.college.set(selected_colleges)

            for profile in memo.college.all():
                user = profile.user
                if user and user.is_active and user.email:
                    notification = Notification(
                        user=user,
                        message=f"New memo published: {memo.title}",
                        url=memo.get_absolute_url(),
                        is_active=True
                    )
                    notification._request = self.request
                    notification._memo_description = memo.description
                    notification.save()

            return response

        except Exception as e:
            print(f"[MemoCreateView ERROR] {str(e)}")
            raise

    def form_invalid(self, form):
        print("[MemoCreateView INVALID FORM]")
        print(form.errors)  # print form errors to terminal
        return super().form_invalid(form)
    
    
class MemoUpdateView(mixins.HybridUpdateView):
    model = Memo
    permissions = ("is_superuser", "director", "OE")
    form_class = forms.MemoForm
    template_name = "masters/memo/memo_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['college'].queryset = UserProfile.objects.filter(user__usertype='College')
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_master"] = True
        context["is_memo"] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        memo = self.object

        selected_colleges = form.cleaned_data.get('college', [])
        memo.college.set(selected_colleges)

        for profile in memo.college.all():
            user = profile.user
            if user and user.is_active and user.email:
                notification = Notification(
                    user=user,
                    message=f"Memo updated: {memo.title}",
                    url=memo.get_absolute_url(),
                    is_active=True
                )
                notification._request = self.request
                notification._memo_description = memo.description
                notification.save()

        return response
    
    
class MemoDeleteView(mixins.HybridDeleteView):
    model = Memo
    permissions = ("is_superuser", "director", "OE")


class CollegeAutocompleteView(View):
    """Autocomplete view for colleges"""
    
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '')
        page = request.GET.get('page', 1)
        
        # Get colleges (UserProfile with user__usertype='College')
        colleges = UserProfile.objects.filter(
            user__usertype='College',
            is_active=True
        )
        
        if q:
            colleges = colleges.filter(
                Q(first_name__icontains=q) | 
                Q(last_name__icontains=q) | 
                Q(email__icontains=q) |
                Q(user__email__icontains=q)
            )
        
        # Paginate results
        paginator = Paginator(colleges, 20)
        try:
            colleges_page = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            colleges_page = paginator.page(1)
        
        results = []
        for college in colleges_page:
            results.append({
                'id': college.id,
                'text': f"{college.fullname()} ({college.email or college.user.email})"
            })
        
        return JsonResponse({
            'results': results,
            'pagination': {
                'more': colleges_page.has_next()
            }
        })