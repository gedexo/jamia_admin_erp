from django import forms

from users.models import UserProfile
from .models import Memo, RequestSubmission, REQUEST_SUBMISSION_STATUS_CHOICES, USERTYPE_CHOICES, RequestSubmissionStatusHistory, RequestSubmissionType
from django.contrib.auth import get_user_model
from tinymce.widgets import TinyMCE 

User = get_user_model()


class RequestStatusUpdateForm(forms.ModelForm):
    reassign_usertype = forms.ChoiceField(
        choices=USERTYPE_CHOICES, required=False, label="Reassign To"
    )
    status = forms.ChoiceField(choices=REQUEST_SUBMISSION_STATUS_CHOICES)
    description = forms.CharField(
        widget=TinyMCE(attrs={"cols": 80, "rows": 15}),
        required=True,
        label="Description",
    )
    remark = forms.CharField(
        widget=TinyMCE(attrs={"cols": 80, "rows": 15}),
        required=True,
        label="Remark",
    )
    user_flow = forms.MultipleChoiceField(
        choices=USERTYPE_CHOICES,
        widget=forms.MultipleHiddenInput(),
        required=False
    )

    class Meta:
        model = RequestSubmission
        fields = [
            'title', 'description', 'attachment',
            'status', 'remark',
            'user_flow', 'reassign_usertype',
        ]

    def __init__(self, *args, **kwargs):
        self.usertype = kwargs.pop('usertype', None)
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        for field in ['title', 'description', 'attachment']:
            self.fields[field].disabled = True  

        if self.usertype != "director":
            self.fields.pop('status', None)
            self.fields.pop('reassign_usertype', None)

        # Hide remark for OE's first submission
        if self.usertype == "OE" and instance:
            oe_history_count = instance.status_history.filter(usertype="OE").count()
            if oe_history_count == 0:
                self.fields.pop('remark', None)

        # Set initial values for hidden fields
        if instance and 'user_flow' in self.fields:
            self.fields['user_flow'].initial = instance.usertype_flow or []

    def clean_user_flow(self):
        return [x for x in self.cleaned_data.get("user_flow", []) if x]

    def clean(self):
        cleaned_data = super().clean()
        re_assign = self.data.get("re_assign") 
        reassign_usertype = cleaned_data.get("reassign_usertype")

        if "reassign_usertype" in self.fields:
            if re_assign == "yes" and not reassign_usertype:
                self.add_error("reassign_usertype", "This field is required when re-assigning.")
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