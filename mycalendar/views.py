from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from mycalendar.forms import MyCalendarForm
from mycalendar.models import MyCalendar


@require_http_methods(["GET", "HEAD", "POST"])
def home(request):
    if request.method == "POST":
        form = MyCalendarForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save()
            if instance.get_ics():
                messages.success(request, _("Calendar generated successfully."))
            else:
                messages.error(request, _("Calendar saved but ICS generation failed; check the CSV format."))
            form = MyCalendarForm()
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = MyCalendarForm()

    context = {
        "form": form,
        "object_list": MyCalendar.objects.order_by("-pk")[:5],
    }
    return render(request, "model_form_upload.html", context)
