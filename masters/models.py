from django.db import models
from tinymce.models import HTMLField
from core.base import BaseModel
from django.urls import reverse_lazy
from django.db.models import Q
from users.models import UserProfile
from core.choices import USERTYPE_CHOICES, REQUEST_SUBMISSION_STATUS_CHOICES, CHOICES


def generate_request_submission_no(prefix="REQ"):
    last_request = RequestSubmission.objects.filter(request_id__startswith=prefix).order_by('-request_id').first()

    if last_request and last_request.request_id:
        try:
            last_id = int(last_request.request_id.replace(prefix, ""))
            next_id = last_id + 1
        except ValueError:
            next_id = 1
    else:
        next_id = 1

    return f"{prefix}{str(next_id).zfill(4)}"


class RequestSubmissionType(BaseModel):
    title = models.CharField(max_length=180)

    def __str__(self):
        return f"{self.title}"

    def get_list_url(self):
        return reverse_lazy("masters:request_submission_type_list")
    
    def get_absolute_url(self):
        return reverse_lazy("masters:request_submission_type_detail", kwargs={"pk": self.pk})

    def get_update_url(self):
        return reverse_lazy("masters:request_submission_type_update", kwargs={"pk": self.pk})

    def get_delete_url(self):
        return reverse_lazy("masters:request_submission_type_delete", kwargs={"pk": self.pk})


class RequestSubmission(BaseModel):
    request_id = models.CharField(max_length=128, unique=True, null=True)
    college = models.ForeignKey("users.UserProfile", related_name="college", on_delete=models.PROTECT,)
    title = models.ForeignKey("masters.RequestSubmissionType", on_delete=models.PROTECT, limit_choices_to={'is_active': True}, null=True)
    description = HTMLField(null=True)
    alternative_description = HTMLField(null=True, blank=True,)
    attachment = models.FileField(upload_to="request_submissions/", blank=True, null=True)
    current_usertype = models.CharField(max_length=30, choices=USERTYPE_CHOICES, null=True)
    request_shared_usertype = models.ManyToManyField(
        "users.UserProfile",
        limit_choices_to=~Q(user__usertype='College'),
        related_name="shared_requests",
        blank=True
    )
    usertype_flow = models.JSONField(default=list, null=True)
    status = models.CharField(max_length=30, choices=REQUEST_SUBMISSION_STATUS_CHOICES, default="forwarded")
    created_by = models.ForeignKey("users.UserProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_submissions")
    updated_by = models.ForeignKey("users.UserProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_submissions")

    def __str__(self):
        return f"{self.title}"

    def save(self, *args, **kwargs):
        if not self.request_id:
            self.request_id = generate_request_submission_no()
        super().save(*args, **kwargs)

    @property
    def director_status(self):
        director_status = self.status_history.filter(usertype="director").order_by("-date").first()
        return director_status.status if director_status else "Pending"

    @property
    def oe_status(self):
        oe_status = self.status_history.filter(usertype="OE").order_by("-date").first()
        return oe_status.status if oe_status else "Pending"

    @property
    def is_approved_or_rejected_for_current_user(self):
        """Check if OE approved/rejected and assigned to the logged-in usertype."""
        from django.middleware import get_current_request

        request = get_current_request()
        if not request or not hasattr(request.user, "profile"):
            return False

        user_profile = request.user.profile
        return self.status in ['approved', 'rejected'] and RequestSubmissionStatusHistory.objects.filter(
            submission=self,
            usertype='OE',
            next_usertype=user_profile.user.usertype,
        ).exists()

    def is_processed_by(self, user_profile):
        return RequestSubmissionStatusHistory.objects.filter(
            submission=self,
            usertype=user_profile.user.usertype,
            submitted_users=user_profile
        ).exists()

    def get_list_url(self):
        return reverse_lazy("masters:my_request_submission_list")

    def get_absolute_url(self):
        return reverse_lazy("masters:request_submission_detail", kwargs={"pk": self.pk})

    def get_update_url(self):
        return reverse_lazy("masters:request_submission_update", kwargs={"pk": self.pk})

    def get_delete_url(self):
        return reverse_lazy("masters:request_submission_delete", kwargs={"pk": self.pk})

    def get_next_user_in_flow(self, current_user_usertype=None):
        if not self.usertype_flow:
            return None

        submitted_usertypes = self.status_history.values_list('usertype', flat=True)

        # Handle normal flow
        try:
            current_index = self.usertype_flow.index(current_user_usertype)
            for next_usertype in self.usertype_flow[current_index + 1:]:
                if next_usertype not in submitted_usertypes:
                    return next_usertype
        except ValueError:
            pass

        return None


class RequestSubmissionStatusHistory(BaseModel):
    submission = models.ForeignKey(RequestSubmission, on_delete=models.CASCADE, related_name='status_history')
    user = models.ForeignKey("users.UserProfile", on_delete=models.SET_NULL, null=True, blank=True)
    submitted_users = models.ManyToManyField("users.UserProfile", related_name="submitted_users")
    usertype = models.CharField(max_length=30, choices=USERTYPE_CHOICES)
    next_usertype = models.CharField(max_length=30, choices=USERTYPE_CHOICES)
    status = models.CharField(max_length=20, choices=REQUEST_SUBMISSION_STATUS_CHOICES, default="forwarded")
    remark = HTMLField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.submission.title} - {self.usertype} - {self.status}"


class Memo(BaseModel):
    title = models.CharField(max_length=180)
    description = HTMLField()
    college = models.ManyToManyField("users.UserProfile", limit_choices_to={'user__usertype': 'College'}, blank=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse_lazy("masters:memo_detail", kwargs={"pk": self.pk})

    def get_update_url(self):
        return reverse_lazy("masters:memo_update", kwargs={"pk": self.pk})

    def get_delete_url(self):
        return reverse_lazy("masters:memo_delete", kwargs={"pk": self.pk})
    