from django.contrib import admin

from .models import MenuItem


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "available", "vegetarian", "vegan", "spicy"]
    list_filter = ["category", "available", "vegetarian", "vegan", "spicy"]
    search_fields = ["name", "description"]
