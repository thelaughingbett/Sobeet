from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response

from base.services import get_free_slots, parse_query_date
from base.services.lookups import get_doctor

from api.serializers import AvailabilitySerializer

from .common import ClinicAPIView
from .openapi import error_response, path_uuid


class DoctorAvailabilityView(ClinicAPIView):
    """GET /doctors/{id}/availability?date=YYYY-MM-DD"""

    @extend_schema(
        tags=["Doctors"],
        summary="Free slots for a doctor on a date",
        description=(
            "Returns every free slot for the doctor on the given clinic-local date, "
            "in time order. Lunch, holidays, time off, booked slots and slots inside "
            "the minimum lead time are excluded. Timestamps carry the clinic's UTC "
            "offset and can be sent straight back when booking."
        ),
        parameters=[
            path_uuid("doctor_id", "The doctor to check."),
            OpenApiParameter(
                "date",
                str,
                OpenApiParameter.QUERY,
                required=True,
                description="Clinic-local date, YYYY-MM-DD.",
            ),
        ],
        responses={
            200: AvailabilitySerializer,
            400: error_response("AVL001: missing or invalid date"),
            404: error_response("DOC001: doctor not found"),
        },
    )
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
