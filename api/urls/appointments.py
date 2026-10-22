from django.urls import path

from api.views import (
    AppointmentCancelView,
    AppointmentCreateView,
    AppointmentRescheduleView,
)

# Ids are matched as plain strings (not <uuid:...>) so a malformed id reaches the
# lookups and returns a coded JSON 404 (APT001) instead of an HTML 404.
urlpatterns = [
    path(
        "appointments",
        AppointmentCreateView.as_view(),
        name="appointment-create"
    ),
    path(
        "appointments/<str:appointment_id>/cancel",
        AppointmentCancelView.as_view(),
        name="appointment-cancel",
    ),
    path(
        "appointments/<str:appointment_id>/reschedule",
        AppointmentRescheduleView.as_view(),
        name="appointment-reschedule",
    ),
]
