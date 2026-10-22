from django.urls import path

from api.views import PatientAppointmentsView, PatientsView

# String id so a malformed value returns the coded JSON 404 (PAT001).
urlpatterns = [
    path(
        'patients',
        PatientsView.as_view(),
        name="patients"
    ),
    path(
        "patients/<str:patient_id>/appointments",
        PatientAppointmentsView.as_view(),
        name="patient-appointments",
    ),
]
