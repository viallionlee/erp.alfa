from django.contrib import admin
from django.contrib.auth.models import Permission
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Unregister the original User admin
admin.site.unregister(User)

class UserAdmin(BaseUserAdmin):
    actions = ['deactivate_selected']

    def deactivate_selected(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} pengguna telah dinonaktifkan.')

    deactivate_selected.short_description = "Nonaktifkan pengguna yang dipilih"

# Register the new User admin
admin.site.register(User, UserAdmin)
admin.site.register(Permission) 