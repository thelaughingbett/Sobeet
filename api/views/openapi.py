"""Small helpers for the @extend_schema decorators, so the views stay readable.

Documentation only: nothing here changes how a request is handled.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse

from api.serializers import ErrorSerializer


def error_response(codes):
    """An error response, described by the error codes that can produce it."""
    return OpenApiResponse(ErrorSerializer, description=codes)


def path_uuid(name, description):
    """A UUID path parameter such as {appointment_id}."""
    return OpenApiParameter(
        name,
        OpenApiTypes.UUID,
        OpenApiParameter.PATH,
        description=description,
    )
