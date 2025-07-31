from django.shortcuts import render
from core import mixins
from core.utils import build_url
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from . import forms
from . import tables
from .models import UserProfile
from .functions import generate_profile_id


class UserProfileListView(mixins.HybridListView):
    model = UserProfile
    table_class = tables.UserProfileTable
    permissions = ("is_superuser", "director", "OE")
    filterset_fields = {}
    search_fields = ("user__email", "employee_id", "first_name","last_name", "mobile", "whatsapp")

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.exclude(user__is_superuser=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_user_profile"] = True
        return context


class CollegeUserProfileListView(mixins.HybridListView):
    model = UserProfile
    table_class = tables.UserProfileTable
    permissions = ("is_superuser", "director", "OE")
    filterset_fields = {}
    search_fields = ("user__email", "employee_id", "first_name","last_name", "mobile", "whatsapp")

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(user__usertype="College")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_college_user_profile"] = True
        return context

    
class UserProfileDetailView(mixins.HybridDetailView):
    queryset = UserProfile.objects.filter(is_active=True)
    template_name = "users/profile.html"
    permissions = ("is_superuser", "director", "OE")


class UserProfileCreateView(mixins.HybridCreateView):
    model = UserProfile
    form_class = forms.UserProfileForm
    permissions = ("is_superuser", "director", "OE")
    template_name = "users/user_profile_form.html"
    exclude = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_users"] = True
        context["is_personal"] = True
        context["is_create"] = True
        context["subtitle"] = "User Profile Personal Data"
        return context

    def get_success_url(self):
        if "save_and_next" in self.request.POST:
            return build_url("accounts:user_create", kwargs={"pk": self.object.pk}, query_params={'type': 'account'})
        return build_url("users:user_profile_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        user = form.save(commit=False)

        if form.cleaned_data.get("password"):
            user.set_password(form.cleaned_data["password"])

        pk = self.kwargs.get("pk")
        if pk:
            user_profile = get_object_or_404(UserProfile, pk=pk)
            user.first_name = user_profile.first_name
            user.last_name = user_profile.last_name or ""
            user.save()

            user_profile.user = user
            user_profile.usertype = user.usertype
            user_profile.photo = user.image
            user_profile.save()
        else:
            user.save()

        return super().form_valid(form)

    def get_success_message(self, cleaned_data):
        return "User Profle Personal Data Created Successfully"


class UserProfileUpdateView(mixins.HybridUpdateView):
    model = UserProfile
    permissions = ("is_superuser", "director", "OE")
    form_class = forms.UserProfileForm
    template_name = "users/user_profile_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial['profile_id'] = generate_profile_id()
        return initial

    def get_form_class(self):
        form_classes = {
            "personal": forms.UserProfileForm,
        }
        info_type = self.request.GET.get("type", "personal")
        return form_classes.get(info_type, forms.UserProfileForm)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        info_type = self.request.GET.get("type", "personal")
        subtitles = {"personal": "Personal Data", "account": "Account"}
        urls = {
            "personal": build_url("users:user_profile_update", kwargs={"pk": self.object.pk}, query_params={'type': 'personal'}),
            "account": build_url("accounts:user_update", kwargs={"pk": self.object.user.pk}) if getattr(self.object, 'user', None) else build_url("accounts:user_create", kwargs={"pk": self.object.pk}, query_params={'type': 'account'}),
        }
        context["title"] = "Edit User Profile"
        context["subtitle"] = subtitles.get(info_type, "Personal Data")
        context['info_type_urls'] = urls
        context["is_personal"] = info_type == "personal"
        context["is_account"] = info_type == "account"
        context["is_update"] = True
        context["is_hrm"] = True
        return context

    def get_success_url(self):
        if "save_and_next" in self.request.POST:
            info_type = self.request.GET.get("type", "personal")
            if info_type == "personal" and self.object.user:
                return build_url("accounts:user_update", kwargs={"pk": self.object.user.pk}, query_params={'type': 'account'})
            elif info_type == "personal":
                return build_url("accounts:user_create", kwargs={"pk": self.object.pk}, query_params={'type': 'account'})
            elif info_type == "account":
                return build_url("users:user_profile_detail", kwargs={"pk": self.object.pk})
            else:
                return build_url("users:user_profile_detail", kwargs={"pk": self.object.pk})
        return self.object.get_list_url()


    def get_success_message(self, cleaned_data):
        info_type = self.request.GET.get("type", "personal")
        messages_dict = {
            "personal": "Personal data updated successfully.",
        }
        return messages_dict.get(info_type, "Data updated successfully.")



class UserProfileDeleteView(mixins.HybridDeleteView):
    model = UserProfile
    permissions = ("is_superuser", "director", "OE")   