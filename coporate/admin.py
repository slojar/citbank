from django.contrib import admin
from .models import Mandate, Institution, Role


class MandateInlineAdmin(admin.TabularInline):
    model = Mandate


class InstitutionModelAdmin(admin.ModelAdmin):
    inlines = [MandateInlineAdmin]
    list_display = ["name", "code", "account_no", "created_on"]
    search_fields = ["name", "code", "account_no"]


admin.site.register(Role)
admin.site.register(Institution, InstitutionModelAdmin)

