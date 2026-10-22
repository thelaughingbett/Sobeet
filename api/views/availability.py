from rest_framework.response import Response

from base.services import get_free_slots, parse_query_date
from base.services.lookups import get_doctor

from .common import ClinicAPIView


class DoctorAvailabilityView(ClinicAPIView):
    """GET /doctors/{id}/availability?date=YYYY-MM-DD"""

    def get(self, request, doctor_id):
        day = parse_query_date(request.query_params.get("date"))
        doctor = get_doctor(doctor_id)
        slots = get_free_slots(doctor, day)
        return Response(
            {
                "doctor_id": str(doctor.pk),
                "date": day.isoformat(),
                "timezone": doctor.clinic.timezone,
                "slots": [slot.to_dict() for slot in slots],
            }
        )
