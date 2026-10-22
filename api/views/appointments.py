from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from base.utils.errors import GEN004
from base.services import (
    book_appointment,
    cancel_appointment,
    parse_start_at,
    reschedule_appointment,
)

from api.serializers import (
    AppointmentSerializer,
    BookingRequestSerializer,
    CancelRequestSerializer,
    RescheduleRequestSerializer,
)

from .common import ClinicAPIView, json_object, require_fields
from .openapi import error_response, path_uuid


class AppointmentCreateView(ClinicAPIView):
    """POST /appointments  { patient_id, doctor_id, start_at }"""

    @extend_schema(
        tags=["Appointments"],
        summary="Book an appointment",
        description=(
            "Books one slot with a doctor. The slot must be on the slot grid, inside "
            "working hours, outside lunch, not a clinic holiday, not in time off, at "
            "least the minimum lead time ahead, and not already taken."
        ),
        request=BookingRequestSerializer,
        responses={
            201: AppointmentSerializer,
            400: error_response("GEN001, GEN004, APT010: malformed or missing input"),
            404: error_response("DOC001, PAT001: doctor or patient not found"),
            409: error_response("APT002: the slot is already taken"),
            422: error_response(
                "DOC002, APT003 to APT009: a booking rule is broken "
                "(doctor not bookable, past, too soon, off the grid, outside hours, "
                "lunch, holiday, time off)"
            ),
        },
    )
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

    @extend_schema(
        tags=["Appointments"],
        summary="Cancel an appointment",
        description=(
            "Cancels a booked appointment and records the reason. "
            "The slot becomes bookable again."
        ),
        parameters=[path_uuid("appointment_id", "The appointment to cancel.")],
        request=CancelRequestSerializer,
        responses={
            200: AppointmentSerializer,
            400: error_response("GEN001, GEN004, APT013: malformed body or missing reason"),
            404: error_response("APT001: appointment not found"),
            409: error_response(
                "APT011, APT012: already cancelled, or not in a booked state"
            ),
        },
    )
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

    @extend_schema(
        tags=["Appointments"],
        summary="Reschedule an appointment",
        description=(
            "Moves a booked appointment to a new slot with the same doctor. The new "
            "slot is validated like a fresh booking. The old appointment becomes "
            "`rescheduled` and frees its slot. The response is the new appointment, "
            "whose `rescheduled_from_id` points back to the old one."
        ),
        parameters=[path_uuid("appointment_id", "The appointment to move.")],
        request=RescheduleRequestSerializer,
        responses={
            200: AppointmentSerializer,
            400: error_response("GEN001, APT010: malformed body or invalid start_at"),
            404: error_response("APT001: appointment not found"),
            409: error_response(
                "APT002, APT011, APT012: new slot taken, or the appointment "
                "is cancelled or not in a booked state"
            ),
            422: error_response(
                "DOC002, APT003 to APT009, APT014: the new slot breaks a booking "
                "rule, or is the same as the current slot"
            ),
        },
    )
    def patch(self, request, appointment_id):
        data = json_object(request)
        start_at = parse_start_at(data.get("start_at"))

        appointment = reschedule_appointment(
            appointment_id=appointment_id,
            start_at=start_at
        )
        return Response(AppointmentSerializer(appointment).data)
