from rest_framework.response import Response
from rest_framework import status

from base.services import list_upcoming_appointments, list_patients, create_patient
from base.utils.errors import GEN004

from api.serializers import AppointmentSerializer, PatientSerializer

from .common import ClinicAPIView, require_fields, json_object


class PatientAppointmentsView(ClinicAPIView):
    """GET /patients/{id}/appointments: upcoming booked appointments, soonest first."""

    def get(self, request, patient_id):
        # PAT001 is raised here if the patient does not exist.
        appointments = list_upcoming_appointments(patient_id=patient_id)
        # The serializer reads the clinic timezone, so load it in the same query.
        appointments = appointments.select_related("doctor__clinic")
        return Response(AppointmentSerializer(appointments, many=True).data)


class PatientsView(ClinicAPIView):
    """GET /patients, POST /patients  { email, full_name, phone_no? }"""

    def get(self, request):
        return Response(PatientSerializer(list_patients(), many=True).data)

    def post(self, request):
        data = json_object(request)
        require_fields(data, "email", "full_name")

        phone_no = data.get("phone_no", "")
        for name in ("email", "full_name", "phone_no"):
            if name in data and not isinstance(data[name], str):
                raise GEN004(detail=f"{name} must be a string.")

        patient = create_patient(
            email=data["email"],
            full_name=data["full_name"],
            phone_no=phone_no,
        )
        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)
