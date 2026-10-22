"""Shared base class and request helpers for the API views."""
import logging
from collections.abc import Mapping

from django.conf import settings
from django.http import Http404

from rest_framework.exceptions import APIException, NotFound, ParseError, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


from base.utils.errors import GEN001, GEN002, GEN004, GEN005, ClinicError

logger = logging.getLogger(__name__)


class ClinicAPIView(APIView):
    """Base for every view. Turns every failure into the one documented error shape.

    Views just raise (or let the services raise) a ClinicError; nothing in a view
    needs its own try/except.
    """

    parser_classes = [JSONParser]
    # Authentication is not part of this version. When accounts are wired in, replace
    # this with IsAuthenticated and read patient_id from request.user instead of the body.
    permission_classes = [AllowAny]

    def handle_exception(self, exc):

        if isinstance(exc, ClinicError):
            return Response(exc.to_dict(), status=exc.status)

        if isinstance(exc, ParseError):
            error = GEN001(detail="Request body is not valid JSON.")
            return Response(error.to_dict(), status=error.status)

        if isinstance(exc, (Http404, NotFound)):
            error = GEN002(detail="The requested resource does not exist.")
            return Response(error.to_dict(), status=error.status)

        if isinstance(exc, APIException):
            # 405, 415, throttling, auth: keep DRF's own handling.
            return super().handle_exception(exc)

        if isinstance(exc, ValidationError):
            error = GEN004(detail=f"Invalid input: {exc.detail}")
            return Response(error.to_dict(), status=error.status)

        # Anything else is a bug. Show the debug page in development,
        # and a coded 500 (with the stack trace in the logs) otherwise.
        if settings.DEBUG:
            return super().handle_exception(exc)
        logger.error(
            "Unhandled error in %s",
            type(self).__name__,
            exc_info=exc
        )

        error = GEN005(detail="Something went wrong on our side.")
        return Response(error.to_dict(), status=error.status)


def json_object(request):
    """The request body, which must be a JSON object."""
    data = request.data
    if not isinstance(data, Mapping):
        raise GEN001(detail="Request body must be a JSON object.")

    return data


def require_fields(data, *names):
    """Raise GEN004 listing every required field that is missing or empty."""
    missing = [name for name in names if data.get(name) in (None, "")]
    if missing:
        raise GEN004(detail="Missing required field(s): " +
                     ", ".join(missing) + ".")
