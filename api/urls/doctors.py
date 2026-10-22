from django.urls import path

from api.views import DoctorAvailabilityView, DoctorsView

# String id so a malformed value returns the coded JSON 404 (DOC001).
urlpatterns = [
    path(
        "doctors",
        DoctorsView.as_view(),
        name="doctors"
    ),
    path(
        "doctors/<str:doctor_id>/availability",
        DoctorAvailabilityView.as_view(),
        name="doctor-availability",
    ),

]
