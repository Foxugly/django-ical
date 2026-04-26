from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from mycalendar.forms import MyCalendarForm
from mycalendar.models import MyCalendar


@require_http_methods(["GET", "POST"])
def home(request):
    if request.method == "POST":
        form = MyCalendarForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save()
            instance.get_ics()
            form = MyCalendarForm()
    else:
        form = MyCalendarForm()

    context = {
        "form": form,
        "object_list": MyCalendar.objects.order_by("-pk")[:5],
    }
    return render(request, "model_form_upload.html", context)
