# Clinic Appointment Booking: System Design

> **Quick links**
>
> - Public URL: [https://sobeet.onrender.com](https://sobeet.onrender.com)
> - API docs (Swagger UI): [https://sobeet.onrender.com/docs](https://sobeet.onrender.com/docs)
> - Postman collection: [Clinic Appointment Booking System](https://www.postman.com/security-meteorologist-10250542-s-team/workspace/clinic-appointment-booking-system)
> - Database schema: [docs/er-diagram.md](docs/er-diagram.md)
> - Error codes: [docs/ERROR_CODES.md](docs/ERROR_CODES.md)
> - AI reflection: [docs/AI_REFLECTION.md](docs/AI_REFLECTION.md)

> **Note on the first load:** the app is hosted on Render's free tier, which puts a service to sleep after about 15 minutes without traffic. The first request after that wakes it up and can take **30 to 60 seconds** (occasionally longer). Every request after that is fast. If the first request times out, wait a moment and retry.

## 1. Problem

A small clinic with 5 doctors needs online appointment booking.

- Each doctor has set working hours and works in 30-minute slots.
- A patient can see the free slots for a doctor on a given day, pick one, and book it.
- A booked slot must never be available to anyone else.
- Patients can cancel.
- The design should start small and be able to grow (more doctors, more branches, more appointment types).

## 2. Guiding principles

1. **Slots are computed, never stored.** There is no `Slot` table. Free slots are derived from working hours minus everything that blocks them. The `Appointment` is the only thing that claims time.
2. **The database enforces the critical invariant.** "No double booking" is a database constraint, not just an application check.
3. **History is kept.** Appointments are never deleted. Every outcome is its own state, so the record is auditable.
4. **Clinic-wide rules live on the clinic; personal rules live on the doctor.** Lunch and holidays belong to `Clinic`; working hours and time off belong to `Doctor`.
5. **Keep v1 small, but leave a clear seam for growth.** Known gaps are listed in section 8.

## 3. Data model

| Model             | Purpose                                                                                                                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Account**       | Login identity (email, password hash, role) and the personal details shared by every kind of user (name, phone). Doctor and Patient are profiles attached to an Account. |
| **Clinic**        | The location. Holds the timezone, slot length, and the lunch window. Present from day one so adding branches later does not need a rewrite.                              |
| **ClinicHoliday** | Clinic-wide closed days. `is_yearly` holidays match on month and day only, so fixed-date holidays do not need re-entering each year.                                     |
| **Doctor**        | Clinical profile: title, speciality, clinic, and lifecycle status.                                                                                                       |
| **WorkingHours**  | One row per doctor per working weekday (for example Monday 09:00-17:00). Weekday numbering starts at Sunday = 1.                                                         |
| **TimeOff**       | A per-doctor absence with a start and end timestamp (leave, sick, conference). Supports multiple future absences and partial days.                                       |
| **Patient**       | Patient profile attached to an Account.                                                                                                                                  |
| **Appointment**   | A claim on a doctor's time. The only table that consumes slots.                                                                                                          |
| **Chart**         | Medical record anchor. Not part of the booking flow (see section 8).                                                                                                     |

[🗃️ Database Schema](docs/er-diagram.md)

## 4. Components

```
Web frontend --> API layer --> Auth/Accounts
                    |
                    +--> Availability service (read-only)
                    +--> Booking service (writes)
                                 |
                              Database
```

| Component                | Responsibility                                                                                                                                                                                                    |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Web frontend**         | Patient UI for choosing a doctor, date, and slot, and for viewing, cancelling, and rescheduling appointments. Separate admin screens for doctors, working hours, time off, holidays, and clinic settings.         |
| **API layer**            | HTTP endpoints. Validates input and calls the services. Contains no business logic.                                                                                                                               |
| **Auth/Accounts**        | Login, roles (patient, doctor, admin), and ownership checks (a patient can only cancel their own appointments).                                                                                                   |
| **Availability service** | Given a doctor and a date, returns free slots. Reads only; writes nothing.                                                                                                                                        |
| **Booking service**      | Creates, cancels, and reschedules appointments. Applies business rules and turns a database constraint violation into "that slot was just taken". Also runs the auto-reschedule routine when time off is created. |
| **Database**             | Source of truth. Enforces no double booking.                                                                                                                                                                      |

Availability and Booking are separate because reads (browsing slots) vastly outnumber writes (booking). Availability can later be cached or served from a replica without touching the booking path.

**Not built in v1: Notifications.** Confirmation and reminder emails or SMS are an obvious future component. See sections 6.3 and 8.

### Main API calls

| Endpoint                                                       | Behaviour                                                                                                                                                                         |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /appointments`                                           | Books a slot. Body: `patient_id`, `doctor_id`, `start_at`. The end time is derived from `Clinic.slot_minutes`.                                                                    |
| `GET /doctors/{id}/availability?date=YYYY-MM-DD`               | Returns all free 30-minute slots for the doctor on that date.                                                                                                                     |
| `PATCH /appointments/{id}/cancel`                              | Body: `reason` (required). Sets state to `cancelled`, stores `cancel_reason` and `cancelled_at`. The slot becomes bookable again.                                                 |
| `PATCH /appointments/{id}/reschedule`                          | Body: `start_at` (the new slot). Validates the new slot exactly like a fresh booking. Marks the old appointment `rescheduled` and creates a new `booked` one pointing back to it. |
| `GET /patients/{id}/appointments` (bonus)                      | Returns the patient's upcoming `booked` appointments, sorted by `start_at` ascending.                                                                                             |
| `POST /doctors/{id}/time-off` (admin, beyond the required set) | Creates time off and auto-reschedules affected appointments (see 6.3).                                                                                                            |

#### Validation rules for booking and rescheduling

Checked in this order, so the first failure gives a specific message:

1. The body is well formed and `start_at` is a valid timestamp.
2. The doctor and patient exist.
3. The doctor is bookable (`active` or `adjunct`).
4. `start_at` falls on a slot boundary (for example 09:00 or 09:30, not 09:10).
5. `start_at` is not in the past.
6. `start_at` is at least 61 minutes from now (`MIN_LEAD_MINUTES = 61`, configurable).
7. The slot is inside the doctor's working hours for that weekday, outside lunch, not on a clinic holiday, and not inside time off.
8. The slot is not already taken (`APT002`), the patient does not already hold it (`APT015`), and the patient has no other booked appointment at the same time (`APT016`). The slot itself is guaranteed by the database constraint, so a race returns 409 instead of double booking.

For reschedule there are two extra checks before the above: the appointment must be in state `booked`, and the new `start_at` must differ from the current one. The whole operation runs in one transaction: mark the old row `rescheduled`, then insert the new `booked` row. If the new slot fails any check, the transaction rolls back and the original stays `booked`.

#### Error responses

Every error returns the same JSON shape with a stable code, for example `APT002` (slot already taken, 409). The full list of codes, their HTTP statuses, and when each is raised is in [docs/ERROR_CODES.md](docs/ERROR_CODES.md).

## 5. Slot calculation

For a given doctor and date (all clinic-local times use `Clinic.timezone`):

1. If the doctor's status is `inactive`, return no slots. (`active` and `adjunct` continue.)
2. If the date is a clinic holiday (exact date, or month and day for yearly holidays), return no slots.
3. Take the doctor's `WorkingHours` for that weekday and cut them into `slot_minutes` pieces.
4. Remove pieces that overlap the lunch window.
5. Remove pieces that overlap any `TimeOff`.
6. Remove pieces that overlap an appointment in state `booked`.
7. Remove pieces that start before `now + MIN_LEAD_MINUTES` (default 61), which also removes everything in the past.

Overlap test for half-open intervals `[start, end)`: `a.start < b.end AND a.end > b.start`. A time off ending at 14:00 does not block the 14:00 slot.

## 6. Key decisions

### 6.1 Compute slots instead of storing them

No `Slot` table means one source of truth and no job to generate or clean up slot rows. When working hours change, the next query reflects it. The cost is a little computation per request, which is trivial at this scale and cacheable later.

### 6.2 Double booking is prevented by the database

Checking "is it free?" and then inserting in application code has a race condition: two patients can pass the check at the same moment. Instead:

- **Minimum:** a partial unique index on `(doctor_id, start_at) WHERE state = 'booked'`.
- **Preferred (Postgres):** an exclusion constraint on `(doctor_id, tstzrange(start_at, end_at)) WHERE state = 'booked'`. This also keeps working if appointment lengths vary later.

The `WHERE state = 'booked'` clause matters. `cancelled` and `rescheduled` rows stay for history and must not block someone else from taking the slot. On a violation, the API returns "that slot was just taken".

The current implementation uses the minimum option, because it works on both SQLite (local development) and Postgres. The exclusion constraint is the planned upgrade once appointment lengths vary.

### 6.3 Time off auto-reschedules affected appointments

When an admin creates a `TimeOff` and booked appointments fall inside it, the system moves them automatically instead of asking the patient. In one database transaction:

1. Insert the `TimeOff`.
2. Find that doctor's `booked` appointments overlapping the window, earliest first.
3. For each, find the earliest free slot with the same doctor after the original start time (using the availability calculation, which now excludes the new time off), within a search horizon (suggested: 14 days).
4. Mark the original `rescheduled` and insert the replacement as `booked` with `rescheduled_from_id` set.
5. If no slot is found within the horizon, mark the appointment `cancelled` and flag it in the admin response so staff can contact the patient.

Doing it in one transaction means a failure leaves nothing half-moved.

### 6.4 Clinic-wide rules on Clinic, per-doctor rules on Doctor

Lunch (`lunch_start`, `lunch_end`) and holidays apply to everyone, so they live on the clinic. That keeps each doctor's `WorkingHours` to one simple block per day. Doctor-specific absences use `TimeOff`.

### 6.5 Account is separate from Doctor and Patient

`Account` is the login identity and holds name and phone. `Doctor` and `Patient` hold role-specific data. One authentication system serves everyone, and one person could in principle be both a doctor and a patient.

### 6.6 Reschedule is cancel-and-create, not an edit

A reschedule never edits an appointment's time. The old row is closed as `rescheduled` and a new row is created pointing back to it. This keeps the slot constraint simple (one row, one slot), preserves the full history, and makes the chain of moves traceable.

### 6.7 Timestamps, with the timezone on the clinic

Appointments and time off use `timestamptz`. Lunch, working hours, and holidays are clinic-local wall-clock values, converted through `Clinic.timezone` when compared. Daylight saving changes and multi-timezone branches are then handled correctly.

### 6.8 Appointments are never deleted

Every outcome is a state. Together with `cancelled_at` and `rescheduled_from_id`, this gives an audit trail without a separate log table.

### 6.9 Minimum lead time

Bookings must be at least `MIN_LEAD_MINUTES` minutes ahead (61 by default, see sections 4 and 5). The rule lives in the availability calculation (so unbookable slots are never shown) and is checked again at booking time, since time passes between viewing and booking. The value is a setting, not a hard-coded number.

### 6.10 Cancellation requires a reason

`PATCH /appointments/{id}/cancel` requires a `reason`, stored in `cancel_reason`. System cancellations (for example no free slot after time off) store a system-generated reason. This also covers part of the cancellation-detail gap in section 8.

### 6.11 Coded business errors

Business failures are raised as `ClinicError` subclasses defined in `base/utils/errors.py`, each with a stable code, a fixed message, and an HTTP status. Views catch `ClinicError` and return one response shape. Codes are never reused, so support and the frontend can rely on them. `CATALOG` allows a test to check that the documentation stays in sync with the code.

## 7. Trade-offs considered

| Decision                                         | Alternative                         | Why we chose this                                                                                                                                |
| ------------------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Computed slots                                   | Pre-generated `Slot` rows           | Less to maintain and no sync problems; at 5 doctors the query cost is negligible.                                                                |
| `TimeOff` table                                  | Enum status on Doctor               | An enum has no time dimension, so it cannot express future or partial-day absences or keep history. `Doctor.status` remains for lifecycle only.  |
| Lunch and holidays as clinic data                | Per-doctor breaks                   | Matches how the clinic actually runs and keeps WorkingHours simple. Staggered lunches would mean moving lunch to the doctor level.               |
| Holidays in a table                              | Config file                         | Admins can edit without a deploy, and it scopes naturally per clinic for multi-branch growth.                                                    |
| `rescheduled` and `cancelled` as separate states | One `cancelled` state with a reason | Better auditability and simpler reporting.                                                                                                       |
| Auto-reschedule on time off                      | Ask the patient to accept or cancel | Much simpler: no notification dependency and no pending-response state. The cost is that patients are moved without being asked (see section 8). |
| Exclusion constraint                             | Application-level check             | Correct under concurrency, with no locking code to maintain. Requires Postgres.                                                                  |
| Chart kept out of booking                        | Single combined record              | Medical data needs different access control and auditing.                                                                                        |

## 8. Known limitations and future work

- **No notifications in v1.** Auto-rescheduled patients are not told. Until notifications exist, the patient's "my appointments" screen must show the new time clearly, and admin staff should receive the list of moved and cancelled appointments when creating time off. Notifications are the first component to add.
- **Auto-reschedule may not suit every patient.** It always picks the earliest slot with the same doctor, which may be inconvenient. A future version could offer choices or allow the patient to undo.
- **Time off is not DB-enforced against bookings.** The unique constraint prevents two bookings in the same slot, but nothing in the database stops a booking landing inside a time-off window. The Booking service re-checks availability inside the booking transaction. A booking made at the exact moment time off is created could still slip through, and the admin flow's reschedule pass should be treated as the safety net.
- **The unique constraint only catches identical start times.** Overlaps with different start times are caught by the application check, not by the database, until the exclusion constraint is adopted.
- **Holiday added after bookings exist.** Adding a holiday hides slots but does not move existing appointments. Decide whether to block the change or apply the same auto-reschedule routine. Yearly holidays on 29 February need a rule for non-leap years.
- **Single lunch window for everyone.** Staggered lunches would require moving lunch to per-doctor settings.
- **Fixed slot length.** `slot_minutes` is clinic-wide. Different appointment types (for example 15 or 60 minutes) would need an `AppointmentType` model. The exclusion constraint already supports variable lengths.
- **Cancellation details.** `cancel_reason` and `cancelled_at` are recorded. Add `cancelled_by` if you need to distinguish patient, admin, and system cancellations.
- **Cold starts on the free host.** After about 15 idle minutes the first request takes 30 to 60 seconds. A paid always-on instance removes it. An external uptime ping can hide it, but it is not a supported fix and is not used here.
- **No authentication on the API yet.** Endpoints accept `patient_id` in the request body. The next step is to require login and read the patient from the authenticated account.
- **Business rules to confirm:** how far ahead patients may book, and a cancellation cutoff (for example 2 hours before). A patient may not hold overlapping appointments (`APT016`).
- **Chart.** Medical records need their own access rules and audit logging before they are built.
- **Growth path:** multi-branch support (already scoped by `Clinic`), caching or read replicas for Availability, notifications, appointment types, and clinic-wide closures (for example, a nullable `doctor_id` on `TimeOff` meaning "everyone").

## 9. Deployment and CI/CD

| Item                       | Details                                                                                                                                    |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Public URL**             | https://sobeet.onrender.com                                                                                                                |
| **Deployment branch**      | `prod`                                                                                                                                     |
| **What triggers a deploy** | Merging a pull request from `dev` into `prod`. Render watches `prod` and automatically builds and deploys every new commit on that branch. |
| **Hosting**                | Render (web service running `gunicorn Sobeet.wsgi:application`)                                                                            |
| **Build command**          | `./build.sh`                                                                                                                               |
| **CI workflow**            | `.github/workflows/django.yml` ("Django CI")                                                                                               |

### Cold starts

The service runs on Render's free instance type, which spins down after about 15 minutes with no incoming requests and starts again on the next one. That first request typically takes 30 to 60 seconds while the container starts, the app loads and the database connects. It is expected behaviour on this tier, not an error, and later requests respond normally. Moving to a paid instance keeps the service running all the time.

### Pipeline

The GitHub Actions workflow runs on every pull request into `dev` or `prod`, and again on every push to either branch. It uses Python 3.12 and does the following, in order:

1. Checks out the code and installs dependencies from `requirements.txt` (with pip caching).
2. Runs `manage.py check` to catch configuration errors.
3. Runs `makemigrations --check --dry-run`, which fails if a model change has no committed migration.
4. Runs the test suite with `manage.py test base api`: service tests (availability, booking, cancel, reschedule, parsing) and endpoint tests (status codes and error shape).
5. Validates the generated OpenAPI schema with `manage.py spectacular --validate --fail-on-warn`, so an endpoint cannot be added without being annotated for the API docs.

### How the gate works

- A pull request from `dev` into `prod` cannot be merged until the `test` check passes, so a failing test blocks the merge. This relies on branch protection on `prod` requiring that check.
- After the merge, Render deploys `prod`. Render's default auto-deploy starts on every push to `prod` without waiting for GitHub Actions, so the protection on `prod` is what guarantees only tested code is deployed. Render's "After CI checks pass" auto-deploy option adds a second guard.

## 10. API collection (Postman)

All endpoints are documented and runnable in the Postman workspace:

**[Clinic Appointment Booking System (Postman)](https://www.postman.com/security-meteorologist-10250542-s-team/workspace/clinic-appointment-booking-system)**

To use it:

1. Open the workspace and fork the collection, or import it into your own Postman.
2. Set the `base_url` variable to the deployed URL (or `http://localhost:8000` for local runs).
3. Run the list request first. A post-response script picks a random `booked` appointment and stores its ID in the `APPOINTMENT_ID` variable, which the cancel and reschedule requests then use.
4. In Postman, use the **Desktop Agent** when testing against localhost.
5. If the deployed service has been idle, the first request wakes it and can take up to a minute (see "Cold starts" in section 9). If it times out, send it again, or raise the request timeout in Postman's settings.

### Generated API docs

The same endpoints are documented from the code itself (drf-spectacular), so they cannot drift from the views:

| URL       | What it is                                                                      |
| --------- | ------------------------------------------------------------------------------- |
| `/docs`   | Swagger UI: browse and try every endpoint.                                      |
| `/redoc`  | ReDoc: a read-only reference view.                                              |
| `/schema` | The raw OpenAPI 3 file. Import this link into Postman to generate a collection. |

## 11. Use of AI

AI tools were used during this project. What they were used for, where their output was wrong, and which decisions were made without them is documented separately in [docs/AI_REFLECTION.md](docs/AI_REFLECTION.md).
