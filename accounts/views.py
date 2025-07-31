from core import mixins
from core.utils import build_url
from users.models import UserProfile

from . import tables
from .forms import UserForm
from .models import User
from django.contrib.auth.views import LoginView
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy


class UserListView(mixins.HybridListView):
    model = User
    table_class = tables.UserTable
    filterset_fields = ("is_active", "is_staff")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Users"
        context["can_add"] = True
        context["new_link"] = reverse_lazy("accounts:user_create")
        return context


class UserDetailView(mixins.HybridDetailView):
    model = User


class UserCreateView(mixins.HybridCreateView):
    model = User
    form_class = UserForm
    permissions = ("director",)
    exclude = None

    def get_template_names(self):
        if "pk" in self.kwargs:
            return "users/user_profile_form.html"
        return super().get_template_names()

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        if "pk" in self.kwargs:
            user_profile = get_object_or_404(UserProfile, pk=self.kwargs["pk"])
            form.fields['email'].initial = user_profile.email if user_profile.email else None
        return form

    def form_valid(self, form):
        # Hash the password before saving the user
        user = form.save(commit=False)
        user.set_password(form.cleaned_data["password"])

        pk = self.kwargs.get("pk")  
        if pk:
            user_profile = get_object_or_404(UserProfile, pk=pk)
            user.first_name = user_profile.first_name
            user.last_name = user_profile.last_name or ""

            user.save()
            user_profile.user = user 
            user_profile.save()

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        urls = {
            "personal": build_url("users:user_profile_update", kwargs={"pk": self.kwargs.get('pk')}, query_params={'type': 'personal'}),
            "account": build_url("accounts:user_create", kwargs={"pk": self.kwargs.get('pk')}, query_params={'type': 'account'}),
        }
        context['info_type_urls'] = urls
        context['title'] = 'New User Profile'
        context['subtitle'] = 'Account Details'
        info_type = self.request.GET.get('type', 'account')
        context['is_personal'] = info_type == 'personal'
        context['is_account'] = info_type == 'account'
        if "pk" in self.kwargs:
            context['object'] = get_object_or_404(UserProfile, pk=self.kwargs["pk"])
        return context

    def get_success_url(self):
        if "save_and_next" in self.request.POST:
            info_type = self.request.GET.get('type', 'account')
            pk = self.kwargs.get('pk')
            if info_type == 'account' and pk:
                return build_url("users:user_profile_detail", kwargs={"pk": pk})
            elif pk:
                return build_url("users:user_profile_update", kwargs={"pk": pk}, query_params={'type': 'account'})
        return reverse_lazy("users:user_profile_list")

    def get_success_message(self, cleaned_data):
        message = "User Profile created successfully"
        return message


class UserUpdateView(mixins.HybridUpdateView):
    model = User
    exclude = None
    fields = ("email", "usertype")
    template_name = "users/user_profile_form.html"
    permissions = ("director",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Edit User Profile"
        context['subtitle'] = "Account Form"
        urls = {
            "personal": build_url("users:user_profile_update", kwargs={"pk": self.object.pk}, query_params={'type': 'personal'}),
            "account": build_url("accounts:user_update", kwargs={"pk": self.object.pk}, query_params={'type': 'account'}),
        }
        info_type = self.request.GET.get('type', 'account')
        context['info_type_urls'] = urls
        context['is_personal'] = info_type == 'personal'
        context['is_account'] = info_type == 'account'
        return context

    def get_success_url(self):
        if "save_and_next" in self.request.POST:
            info_type = self.request.GET.get('type', 'account')
            if info_type == 'account' and hasattr(self.object, 'user_profile'):
                return build_url("users:user_profile_detail", kwargs={"pk": self.object.user_profile.pk})
            elif hasattr(self.object, 'user_profile'):
                return build_url("users:user_profile_update", kwargs={"pk": self.object.user_profile.pk}, query_params={'type': 'personal'})
        return reverse_lazy("users:user_profile_list")


class UserDeleteView(mixins.HybridDeleteView):
    model = User