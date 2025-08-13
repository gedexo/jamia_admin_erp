from django import forms
from core.base import BaseForm
from users.models import UserProfile
from .models import Memo, RequestSubmission, USERTYPE_CHOICES, RequestSubmissionStatusHistory, RequestSubmissionType
from django.contrib.auth import get_user_model
from tinymce.widgets import TinyMCE 

User = get_user_model()

REQUEST_STATUS_CHOICES = (
    ("re_assign", "Re Assign"), ("approved", "Approved"), ("rejected", "Rejected"),
)

class RequestStatusUpdateForm(forms.ModelForm):
    reassign_usertype = forms.ChoiceField(
        choices=USERTYPE_CHOICES,
        required=False,
        label="Reassign To"
    )
    status = forms.ChoiceField(
        choices=REQUEST_STATUS_CHOICES,
        label="Status"
    )
    description = forms.CharField(
        widget=TinyMCE(attrs={"cols": 80, "rows": 15}),
        required=True,
        label="Description"
    )
    remark = forms.CharField(
        widget=TinyMCE(attrs={"cols": 80, "rows": 15}),
        required=True,
        label="Remark"
    )
    user_flow = forms.MultipleChoiceField(
        choices=USERTYPE_CHOICES,
        widget=forms.MultipleHiddenInput(),
        required=False
    )

    # Show only for OE after director approved/rejected
    share_request = forms.ChoiceField(
        choices=[("no", "No"), ("yes", "Yes")],
        required=False,
        label="Did you want to share this request?"
    )
    
    class Meta:
        model = RequestSubmission
        fields = [
            'title', 'description', 'alternative_description', 'attachment',
            'status', 'remark',
            'user_flow', 'reassign_usertype',
            'share_request', 'request_shared_usertype'
        ]

    def __init__(self, *args, **kwargs):
        self.usertype = kwargs.pop('usertype', None)
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # Disable title, description, attachment
        for field in ['title', 'description', 'attachment']:
            self.fields[field].disabled = True  

        # Only director sees status and reassign
        if self.usertype != "director":
            self.fields.pop('status', None)
            self.fields.pop('reassign_usertype', None)

        # Remark handling for OE
        if self.usertype == "OE" and instance:
            oe_history_count = instance.status_history.filter(usertype="OE").count()
            if oe_history_count == 0:
                self.fields.pop('remark', None)
            else:
                self.fields.pop('alternative_description', None)
        else:
            self.fields.pop('alternative_description', None)

        # Director remark optional
        if self.usertype == "director":
            self.fields["remark"].required = False

        # Only show share_request for OE after director approved/rejected
        if self.usertype == "OE" and instance:
            director_history = instance.status_history.filter(usertype="director").order_by("-date").first()
            if not director_history or director_history.status not in ["approved", "rejected"]:
                self.fields.pop("share_request", None)
                self.fields.pop("request_shared_usertype", None)
        else:
            self.fields.pop("share_request", None)
            self.fields.pop("request_shared_usertype", None)

        # Initialize hidden user_flow
        if instance and 'user_flow' in self.fields:
            self.fields['user_flow'].initial = instance.usertype_flow or []

    def clean_user_flow(self):
        return [x for x in self.cleaned_data.get("user_flow", []) if x]

    def clean(self):
        cleaned_data = super().clean()

        # Validate reassign_usertype if director chose to re-assign
        re_assign = self.data.get("re_assign")
        reassign_usertype = cleaned_data.get("reassign_usertype")
        if "reassign_usertype" in self.fields and re_assign == "yes" and not reassign_usertype:
            self.add_error("reassign_usertype", "This field is required when re-assigning.")

        # Ensure request_shared_usertype has value if share_request = yes
        share_request = cleaned_data.get("share_request")
        shared_users = cleaned_data.get("request_shared_usertype")
        if "request_shared_usertype" in self.fields and share_request == "yes" and not shared_users:
            self.add_error("request_shared_usertype", "Please select at least one usertype to share the request with.")

        return cleaned_data
    
class RequestSubmissionTypeForm(forms.ModelForm):
    class Meta:
        model = RequestSubmissionType
        fields = ['title',]


class MemoForm(forms.ModelForm):
    college = forms.ModelMultipleChoiceField(
        queryset=UserProfile.objects.none(),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select colleges...'
        }),
        required=False,
        label="College"
    )

    class Meta:
        model = Memo
        fields = ['title', 'description', 'college']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['college'].queryset = UserProfile.objects.filter(user__usertype='College', is_active=True)