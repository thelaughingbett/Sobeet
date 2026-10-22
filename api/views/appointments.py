from rest_framework import status
from rest_framework.response import Response

from base.utils.errors import GEN004
from base.services import (
    book_appointment,
    cancel_appointment,
    parse_start_at,
    reschedule_appointment,
)

from api.serializers import AppointmentSerializer

from .common import ClinicAPIView, json_object, require_fields


class AppointmentCreateView(ClinicAPIView):
    """POST /appointments  { patient_id, doctor_id, start_at }"""

    def post(self, request):
        data = json_object(request)
        require_fields(data, "patient_id", "doctor_id")
        start_at = parse_start_at(data.get("start_at"))

        appointment = book_appointment(
            patient_id=data["patient_id"],
            doctor_id=data["doctor_id"],
            start_at=start_at,
        )
        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_201_CREATED
        )


class AppointmentCancelView(ClinicAPIView):
    """PATCH /appointments/{id}/cancel  { reason }"""

    def patch(self, request, appointment_id):
        data = json_object(request)
        reason = data.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise GEN004(detail="reason must be a string.")

        appointment = cancel_appointment(
            appointment_id=appointment_id,
            reason=reason
        )
        return Response(AppointmentSerializer(appointment).data)


class AppointmentRescheduleView(ClinicAPIView):
    """PATCH /appointments/{id}/reschedule  { start_at }

    Returns the new appointment, which points back to the old one
    through rescheduled_from_id.
    """

    def patch(self, request, appointment_id):
        data = json_object(request)
        start_at = parse_start_at(data.get("start_at"))

        appointment = reschedule_appointment(
            appointment_id=appointment_id,
            start_at=start_at
        )
        return Response(AppointmentSerializer(appointment).data)
