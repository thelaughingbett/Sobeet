from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response

from api.serializers import DoctorCreateRequestSerializer, DoctorSerializer
from base.services import create_doctor, list_doctors
from base.utils.errors import GEN004

from .common import ClinicAPIView, json_object, require_fields
from .openapi import error_response


class DoctorsView(ClinicAPIView):
    """GET /doctors?clinic_id=&status=
    POST /doctors  { email, full_name, clinic_id, phone_no?, title?, speciality?, status?, working_hours? }
    """

    @extend_schema(
        tags=["Doctors"],
        summary="List doctors",
        description="Lists doctors, optionally filtered by clinic and status.",
        parameters=[
            OpenApiParameter(
                "clinic_id",
                str,
                OpenApiParameter.QUERY,
                required=False,
                description="Only doctors that belong to this clinic.",
            ),
            OpenApiParameter(
                "status",
                str,
                OpenApiParameter.QUERY,
                required=False,
                enum=["active", "adjunct", "inactive"],
                description="Only doctors with this status.",
            ),
        ],
        responses={200: DoctorSerializer(many=True)},
    )
    def get(self, request):
        doctors = list_doctors(
            clinic_id=request.query_params.get("clinic_id"),
            status=request.query_params.get("status"),
        )
        return Response(DoctorSerializer(doctors, many=True).data)

    @extend_schema(
        tags=["Doctors"],
        summary="Create a doctor",
        description=(
            "Creates the doctor's account and profile, and optionally their working "
            "hours (one block per weekday, Sunday = 1 to Saturday = 7)."
        ),
        request=DoctorCreateRequestSerializer,
        responses={
            201: DoctorSerializer,
            400: error_response("GEN001, GEN004: malformed or missing input"),
            404: error_response("CLN001: clinic not found"),
            409: error_response("USR002: email already registered"),
        },
    )
    def post(self, request):
        data = json_object(request)
        require_fields(data, "email", "full_name", "clinic_id")

        for name in ("email", "full_name", "clinic_id", "phone_no",
                     "title", "speciality", "status"):
            if name in data and not isinstance(data[name], str):
                raise GEN004(detail=f"{name} must be a string.")

        doctor = create_doctor(
            email=data["email"],
            full_name=data["full_name"],
            clinic_id=data["clinic_id"],
            phone_no=data.get("phone_no", ""),
            title=data.get("title", ""),
            speciality=data.get("speciality", ""),
            status=data.get("status", "active"),
            working_hours=data.get("working_hours", []),
        )
        return Response(DoctorSerializer(doctor).data, status=status.HTTP_201_CREATED)
