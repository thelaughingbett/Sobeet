from rest_framework import status
from rest_framework.response import Response

from api.serializers import DoctorSerializer
from base.services import create_doctor, list_doctors
from base.utils.errors import GEN004

from .common import ClinicAPIView, json_object, require_fields


class DoctorsView(ClinicAPIView):
    """GET /doctors?clinic_id=&status=
    POST /doctors  { email, full_name, clinic_id, phone_no?, title?, speciality?, status?, working_hours? }
    """

    def get(self, request):
        doctors = list_doctors(
            clinic_id=request.query_params.get("clinic_id"),
            status=request.query_params.get("status"),
        )
        return Response(DoctorSerializer(doctors, many=True).data)

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
