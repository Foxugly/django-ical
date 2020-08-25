from django.contrib import admin
from mycalendar.models import MyCalendar
# Register your models here.


class MyCalendarAdmin(admin.ModelAdmin):
    pass


admin.site.register(MyCalendar, MyCalendarAdmin)
