"""Output serializers. Input is validated by the services and the parsing helpers,
so that every failure goes through the same coded errors."""
from base.models import Doctor, WorkingHours
from base.models import Patient
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from base.services.timeutils import clinic_tz


def _local_iso(appointment, value):
    """ISO timestamp in the clinic's timezone, matching what availability returns."""
    if value is None:
        return None
    return value.astimezone(clinic_tz(appointment.doctor.clinic)).isoformat()


class AppointmentSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    patient_id = serializers.UUIDField(read_only=True)
    doctor_id = serializers.UUIDField(read_only=True)
    doctor_name = serializers.SerializerMethodField()
    start_at = serializers.SerializerMethodField()
    end_at = serializers.SerializerMethodField()
    state = serializers.CharField(read_only=True)
    cancelled_at = serializers.SerializerMethodField()
    cancel_reason = serializers.CharField(read_only=True)
    rescheduled_from_id = serializers.UUIDField(
        read_only=True, allow_null=True)

    # The @extend_schema_field decorators below only tell the API docs what type each
    # method returns. They do not change the response.
    def get_doctor_name(self, obj) -> str:
        return str(obj.doctor)

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_start_at(self, obj):
        return _local_iso(obj, obj.start_at)

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_end_at(self, obj):
        return _local_iso(obj, obj.end_at)

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_cancelled_at(self, obj):
        return _local_iso(obj, obj.cancelled_at)


class PatientSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        source="account.email",
        read_only=True
    )

    full_name = serializers.CharField(
        source="account.full_name",
        read_only=True
    )

    phone_no = serializers.CharField(
        source="account.phone_no",
        read_only=True
    )

    class Meta:
        model = Patient
        fields = ["id", "email", "full_name", "phone_no"]


class WorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = ["weekday", "start_time", "end_time"]


class DoctorSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="account.email", read_only=True)
    full_name = serializers.CharField(
        source="account.full_name",
        read_only=True
    )
    phone_no = serializers.CharField(source="account.phone_no", read_only=True)
    clinic_id = serializers.CharField(read_only=True)
    working_hours = WorkingHoursSerializer(many=True, read_only=True)

    class Meta:
        model = Doctor
        fields = [
            "id",
            "email",
            "full_name",
            "phone_no",
            "clinic_id",
            "title",
            "speciality",
            "status",
            "working_hours",
        ]


# ── Documentation-only serializers ────────────────────────────────
# These describe request bodies and shared response shapes for the API docs
# (drf-spectacular). The views do not use them to validate or build responses.


class BookingRequestSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    doctor_id = serializers.UUIDField()
    start_at = serializers.DateTimeField(
        help_text="ISO 8601 with a UTC offset, e.g. 2026-11-03T10:00:00+03:00"
    )


class CancelRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(
        help_text="Why the appointment is being cancelled.")


class RescheduleRequestSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField(
        help_text="The new slot, ISO 8601 with a UTC offset."
    )


class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField(
        help_text="Display text ending in (Ref: CODE).")
    code = serializers.CharField(help_text="Stable error code, e.g. APT002.")
    message = serializers.CharField(
        help_text="Short, fixed description of the error.")
    detail = serializers.CharField(
        allow_blank=True, help_text="Specific explanation for this occurrence."
    )


class SlotSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()


class AvailabilitySerializer(serializers.Serializer):
    doctor_id = serializers.UUIDField()
    date = serializers.DateField()
    timezone = serializers.CharField(
        help_text="The clinic's IANA timezone name.")
    slots = SlotSerializer(many=True)


class DoctorCreateRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField()
    clinic_id = serializers.UUIDField()
    phone_no = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField(required=False, allow_blank=True)
    speciality = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=Doctor.Status.choices, required=False, default=Doctor.Status.ACTIVE
    )
    working_hours = WorkingHoursSerializer(many=True, required=False)


class PatientCreateRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField()
    phone_no = serializers.CharField(required=False, allow_blank=True)
