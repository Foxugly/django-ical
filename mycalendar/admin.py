from django.contrib import admin

from mycalendar.models import MyCalendar


@admin.register(MyCalendar)
class MyCalendarAdmin(admin.ModelAdmin):
    list_display = ("pk", "name", "uploaded_at", "has_ics")
    list_filter = ("uploaded_at",)
    search_fields = ("name",)
    ordering = ("-uploaded_at",)
    readonly_fields = ("uploaded_at",)

    @admin.display(boolean=True, description="ICS")
    def has_ics(self, obj):
        return bool(obj.ics and obj.ics.name)
