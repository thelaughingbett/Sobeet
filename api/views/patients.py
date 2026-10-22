from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from base.services import list_upcoming_appointments, list_patients, create_patient
from base.utils.errors import GEN004

from api.serializers import (
    AppointmentSerializer,
    PatientCreateRequestSerializer,
    PatientSerializer,
)

from .common import ClinicAPIView, require_fields, json_object
from .openapi import error_response, path_uuid


class PatientAppointmentsView(ClinicAPIView):
    """GET /patients/{id}/appointments: upcoming booked appointments, soonest first."""

    @extend_schema(
        tags=["Patients"],
        summary="A patient's upcoming appointments",
        description=(
            "Lists the patient's upcoming `booked` appointments, soonest first. "
            "Cancelled, rescheduled and past appointments are not included."
        ),
        parameters=[
            path_uuid("patient_id", "The patient whose appointments to list.")],
        responses={
            200: AppointmentSerializer(many=True),
            404: error_response("PAT001: patient not found"),
        },
    )
    def get(self, request, patient_id):
        # PAT001 is raised here if the patient does not exist.
        appointments = list_upcoming_appointments(patient_id=patient_id)
        # The serializer reads the clinic timezone, so load it in the same query.
        appointments = appointments.select_related("doctor__clinic")
        return Response(AppointmentSerializer(appointments, many=True).data)


class PatientsView(ClinicAPIView):
    """GET /patients, POST /patients  { email, full_name, phone_no? }"""

    @extend_schema(
        tags=["Patients"],
        summary="List patients",
        description="Lists all patients.",
        responses={200: PatientSerializer(many=True)},
    )
    def get(self, request):
        return Response(PatientSerializer(list_patients(), many=True).data)

    @extend_schema(
        tags=["Patients"],
        summary="Create a patient",
        description="Creates the patient's account and profile.",
        request=PatientCreateRequestSerializer,
        responses={
            201: PatientSerializer,
            400: error_response("GEN001, GEN004: malformed or missing input"),
            409: error_response("USR002: email already registered"),
        },
    )
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
