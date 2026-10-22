# Error Codes

Every business error in the clinic booking system has a stable code. The code is defined once in `base/utils/errors.py` and listed here for support staff, frontend developers, and API consumers.

## How errors work

Code raises a `ClinicError` (for example `raise APT002(detail="...")`). The view catches it and returns `exc.to_response()`.

### Response shape

```json
{
  "error": "That slot is already booked for Dr. Amina at 10:00. (Ref: APT002)",
  "code": "APT002",
  "message": "Slot already taken",
  "detail": "That slot is already booked for Dr. Amina at 10:00."
}
```

| Field     | Purpose                                                                                                                               |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `error`   | Ready-to-display text: the detail (or the message if there is no detail) followed by `(Ref: CODE)`. The frontend can show this as is. |
| `code`    | Stable identifier. Branch on this in code, never on the message text.                                                                 |
| `message` | Short, fixed description of the error class.                                                                                          |
| `detail`  | Specific explanation for this occurrence. May be empty.                                                                               |

### Code prefixes

| Prefix | Area                                             |
| ------ | ------------------------------------------------ |
| `GEN`  | General                                          |
| `USR`  | Users and authentication                         |
| `PAT`  | Patients                                         |
| `DOC`  | Doctors                                          |
| `CLN`  | Clinic settings and holidays                     |
| `WKH`  | Doctor working hours                             |
| `TOF`  | Doctor time off                                  |
| `AVL`  | Availability queries                             |
| `APT`  | Appointments (booking, cancelling, rescheduling) |

### HTTP status conventions

| Status | Meaning in this system                                                                                          |
| ------ | --------------------------------------------------------------------------------------------------------------- |
| `400`  | The request is malformed or missing data (bad JSON, bad date, missing reason).                                  |
| `401`  | Not authenticated.                                                                                              |
| `403`  | Authenticated but not allowed.                                                                                  |
| `404`  | The referenced record does not exist.                                                                           |
| `409`  | The request conflicts with current state (slot taken, already cancelled, duplicate).                            |
| `422`  | The request is well formed but breaks a booking rule (past, too soon, outside hours, lunch, holiday, time off). |
| `500`  | Unexpected server failure.                                                                                      |

## Codes

### General

| Code     | HTTP | Message             | When it happens                                                                                                         |
| -------- | ---- | ------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `GEN001` | 400  | Bad request payload | Body is not valid JSON or is not an object.                                                                             |
| `GEN002` | 404  | Not found           | The requested resource or route does not exist.                                                                         |
| `GEN003` | 403  | Not permitted       | The caller is authenticated but not allowed to do this (for example a patient acting on another patient's appointment). |
| `GEN004` | 400  | Validation failed   | One or more fields are missing or invalid. List them in `detail`.                                                       |
| `GEN005` | 500  | Unexpected error    | An unhandled failure. Log the stack trace and quote the reference to support.                                           |

### Users and authentication

| Code     | HTTP | Message                  | When it happens                                        |
| -------- | ---- | ------------------------ | ------------------------------------------------------ |
| `USR001` | 404  | User not found           | No account matches the given id or email.              |
| `USR002` | 409  | Email already registered | Registering with an email that already has an account. |
| `USR003` | 401  | Invalid credentials      | Wrong email or password. Do not say which.             |
| `USR004` | 403  | Account inactive         | The account has been deactivated.                      |

### Patients

| Code     | HTTP | Message                        | When it happens                            |
| -------- | ---- | ------------------------------ | ------------------------------------------ |
| `PAT001` | 404  | Patient not found              | No patient matches the given id.           |
| `PAT002` | 409  | Patient profile already exists | The account already has a patient profile. |

### Doctors

| Code     | HTTP | Message                       | When it happens                                                                 |
| -------- | ---- | ----------------------------- | ------------------------------------------------------------------------------- |
| `DOC001` | 404  | Doctor not found              | No doctor matches the given id.                                                 |
| `DOC002` | 422  | Doctor is not bookable        | The doctor's status is `inactive`. `active` and `adjunct` doctors are bookable. |
| `DOC003` | 409  | Doctor profile already exists | The account already has a doctor profile.                                       |

### Clinic and holidays

| Code     | HTTP | Message                  | When it happens                                    |
| -------- | ---- | ------------------------ | -------------------------------------------------- |
| `CLN001` | 404  | Clinic not found         | No clinic matches the given id.                    |
| `CLN002` | 400  | Invalid lunch window     | `lunch_end` is not after `lunch_start`.            |
| `CLN003` | 409  | Duplicate clinic holiday | A holiday already exists for that clinic and date. |

### Working hours

| Code     | HTTP | Message                     | When it happens                                                                  |
| -------- | ---- | --------------------------- | -------------------------------------------------------------------------------- |
| `WKH001` | 404  | Working hours not found     | No working hours row matches the given id.                                       |
| `WKH002` | 400  | Invalid working hours range | `end_time` is not after `start_time`.                                            |
| `WKH003` | 409  | Overlapping working hours   | The doctor already has working hours overlapping this block on the same weekday. |
| `WKH004` | 400  | Invalid weekday             | Weekday is outside 1 to 7 (Sunday = 1, Saturday = 7).                            |

### Time off

| Code     | HTTP | Message                | When it happens                          |
| -------- | ---- | ---------------------- | ---------------------------------------- |
| `TOF001` | 404  | Time off not found     | No time off record matches the given id. |
| `TOF002` | 400  | Invalid time-off range | `end_at` is not after `start_at`.        |

### Availability

| Code     | HTTP | Message                 | When it happens                                                                            |
| -------- | ---- | ----------------------- | ------------------------------------------------------------------------------------------ |
| `AVL001` | 400  | Missing or invalid date | `GET /doctors/{id}/availability` called without a `date`, or the date is not `YYYY-MM-DD`. |

### Appointments: booking and validation

These apply to both `POST /appointments` and `PATCH /appointments/{id}/reschedule` (the new slot is validated like a fresh booking).

| Code     | HTTP | Message                                      | When it happens                                                                                                                                               |
| -------- | ---- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `APT001` | 404  | Appointment not found                        | No appointment matches the given id.                                                                                                                          |
| `APT002` | 409  | Slot already taken                           | Another `booked` appointment holds the slot. Also returned when the database constraint rejects a simultaneous booking. The patient should pick another slot. |
| `APT003` | 422  | Slot is in the past                          | `start_at` is earlier than now.                                                                                                                               |
| `APT004` | 422  | Slot is within the minimum booking lead time | `start_at` is less than 60 minutes from now (`MIN_LEAD_MINUTES`).                                                                                             |
| `APT005` | 422  | Start time is not on a slot boundary         | `start_at` does not line up with `slot_minutes` (for example 09:10 with 30-minute slots).                                                                     |
| `APT006` | 422  | Slot is outside the doctor's working hours   | The doctor has no working hours covering the slot on that weekday.                                                                                            |
| `APT007` | 422  | Slot falls in the lunch break                | The slot overlaps the clinic lunch window.                                                                                                                    |
| `APT008` | 422  | Clinic is closed on this date                | The date is a clinic holiday.                                                                                                                                 |
| `APT009` | 422  | Doctor is on time off                        | The slot overlaps one of the doctor's time-off records.                                                                                                       |
| `APT010` | 400  | Invalid or missing start time                | `start_at` is absent or not a valid timestamp.                                                                                                                |
| `APT015` | 409  | You already hold this slot                   | The patient already holds a `booked` appointment with this doctor in the slot. Returned instead of `APT002`, which is for a slot held by someone else.        |
| `APT016` | 409  | You have another appointment at this time    | The patient already has a `booked` appointment with a different doctor that overlaps the slot. A patient cannot be in two places at once.                     |

### Appointments: cancel and reschedule

| Code     | HTTP | Message                                  | When it happens                                                                            |
| -------- | ---- | ---------------------------------------- | ------------------------------------------------------------------------------------------ |
| `APT011` | 409  | Appointment already cancelled            | Cancelling, or rescheduling, an appointment whose state is `cancelled`.                    |
| `APT012` | 409  | Appointment is not in a booked state     | Cancelling or rescheduling an appointment that is `rescheduled`, `executed`, or `no_show`. |
| `APT013` | 400  | Cancellation reason is required          | `PATCH /appointments/{id}/cancel` was sent without a non-empty `reason`.                   |
| `APT014` | 422  | New slot is the same as the current slot | The reschedule target equals the appointment's current `start_at`.                         |

## Which error comes first

Booking and reschedule validation runs in a fixed order, so a request that breaks several rules always gets the same error:

1. Payload and timestamp format (`GEN001`, `GEN004`, `APT010`)
2. Doctor and patient exist (`DOC001`, `PAT001`)
3. Doctor is bookable (`DOC002`)
4. Slot boundary (`APT005`)
5. Past (`APT003`), then minimum lead time (`APT004`)
6. Working hours, lunch, holiday, time off (`APT006`, `APT007`, `APT008`, `APT009`)
7. Slot already taken (`APT002`), or already held by this patient (`APT015`)
8. Patient has an overlapping appointment with another doctor (`APT016`)

For reschedule, `APT001`, `APT011`, `APT012`, and `APT014` are checked first, before the steps above.
