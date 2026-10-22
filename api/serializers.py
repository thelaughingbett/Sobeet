"""Output serializers. Input is validated by the services and the parsing helpers,
so that every failure goes through the same coded errors."""
from base.models import Doctor, WorkingHours
from base.models import Patient
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
    rescheduled_from_id = serializers.UUIDField(read_only=True)

    def get_doctor_name(self, obj):
        return str(obj.doctor)

    def get_start_at(self, obj):
        return _local_iso(obj, obj.start_at)

    def get_end_at(self, obj):
        return _local_iso(obj, obj.end_at)

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
