"""
Business error codes (see docs/ERROR_CODES.md). Raise them, catch ClinicError
at the view edge, return exc.to_response().

    raise APT002(detail="Dr. Amina is already booked at 10:00 on 2026-11-03.")
    except ClinicError as exc:
        return exc.to_response()

The JSON keeps a single {"error": "..."} key the front-end can show directly,
and adds code / message / detail for support.
"""
from django.http import JsonResponse


class ClinicError(Exception):
    def __init__(self, code, message, detail="", status=400, **context):
        self.code = code
        self.message = message
        self.detail = detail
        self.status = status
        self.context = context
        super().__init__(f"[{code}] {message}")

    @property
    def text(self):
        """What the person sees: the detail if there is one, plus the code to quote to support."""
        return f"{self.detail or self.message} (Ref: {self.code})"

    def to_dict(self):
        return {"error": self.text, "code": self.code,
                "message": self.message, "detail": self.detail}

    def to_response(self):
        return JsonResponse(self.to_dict(), status=self.status)


CATALOG = {}   # code -> (message, http status), for support tooling and tests


def _define(code, message, status=400):
    CATALOG[code] = (message, status)

    def make(detail="", **context):
        return ClinicError(code, message, detail, status, **context)
    make.code = code
    return make


# ── General ───────────────────────────────────────────────────────
GEN001 = _define("GEN001", "Bad request payload", 400)
GEN002 = _define("GEN002", "Not found", 404)
GEN003 = _define("GEN003", "Not permitted", 403)
GEN004 = _define("GEN004", "Validation failed", 400)
GEN005 = _define("GEN005", "Unexpected error", 500)

# ── User & Auth ───────────────────────────────────────────────────
USR001 = _define("USR001", "User not found", 404)
USR002 = _define("USR002", "Email already registered", 409)
USR003 = _define("USR003", "Invalid credentials", 401)
USR004 = _define("USR004", "Account inactive", 403)

# ── Patient ───────────────────────────────────────────────────────
PAT001 = _define("PAT001", "Patient not found", 404)
PAT002 = _define("PAT002", "Patient profile already exists", 409)

# ── Doctor ────────────────────────────────────────────────────────
DOC001 = _define("DOC001", "Doctor not found", 404)
DOC002 = _define("DOC002", "Doctor is not bookable", 422)
DOC003 = _define("DOC003", "Doctor profile already exists", 409)

# ── Clinic & Holidays ─────────────────────────────────────────────
CLN001 = _define("CLN001", "Clinic not found", 404)
CLN002 = _define("CLN002", "Invalid lunch window", 400)
CLN003 = _define("CLN003", "Duplicate clinic holiday", 409)

# ── Working Hours ─────────────────────────────────────────────────
WKH001 = _define("WKH001", "Working hours not found", 404)
WKH002 = _define("WKH002", "Invalid working hours range", 400)
WKH003 = _define("WKH003", "Overlapping working hours", 409)
WKH004 = _define("WKH004", "Invalid weekday", 400)

# ── Time Off ──────────────────────────────────────────────────────
TOF001 = _define("TOF001", "Time off not found", 404)
TOF002 = _define("TOF002", "Invalid time-off range", 400)

# ── Availability ──────────────────────────────────────────────────
AVL001 = _define("AVL001", "Missing or invalid date", 400)

# ── Appointments: booking & validation ────────────────────────────
APT001 = _define("APT001", "Appointment not found", 404)
APT002 = _define("APT002", "Slot already taken", 409)
APT003 = _define("APT003", "Slot is in the past", 422)
APT004 = _define("APT004", "Slot is within the minimum booking lead time", 422)
APT005 = _define("APT005", "Start time is not on a slot boundary", 422)
APT006 = _define("APT006", "Slot is outside the doctor's working hours", 422)
APT007 = _define("APT007", "Slot falls in the lunch break", 422)
APT008 = _define("APT008", "Clinic is closed on this date", 422)
APT009 = _define("APT009", "Doctor is on time off", 422)
APT010 = _define("APT010", "Invalid or missing start time", 400)

# ── Appointments: cancel & reschedule ─────────────────────────────
APT011 = _define("APT011", "Appointment already cancelled", 409)
APT012 = _define("APT012", "Appointment is not in a booked state", 409)
APT013 = _define("APT013", "Cancellation reason is required", 400)
APT014 = _define("APT014", "New slot is the same as the current slot", 422)
