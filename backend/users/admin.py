from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = [
        "email",
        "username",
        "role",
        "customer_id",
        "is_active",
        "date_joined",
    ]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "username", "phone"]
    ordering = ["-date_joined"]

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone", "customer_id")}),
        ("Roles & permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "username", "password1", "password2", "phone", "role")}),
    )
