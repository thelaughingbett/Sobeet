from .appointments import urlpatterns as appointment_urls
from .doctors import urlpatterns as doctor_urls
from .patients import urlpatterns as patient_urls

urlpatterns = [
    *appointment_urls,
    *doctor_urls,
    *patient_urls,
]
