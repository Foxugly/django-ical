from django import forms
from mycalendar.models import MyCalendar


class MyCalendarForm(forms.ModelForm):
    class Meta:
        model = MyCalendar
        fields = ('name', 'document', )
