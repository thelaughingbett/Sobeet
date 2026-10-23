# How to Go Through the System

A guided tour of the booking flow using plain HTTP requests: find a doctor, create a patient, check availability, book, then reschedule and cancel. Follow the steps in order and every id you need is in the previous response.

For the design behind each step, see the [README](../README.md). For every error code, see [ERROR_CODES.md](ERROR_CODES.md).

## Before you start

| Item                | Value                                                                                                                            |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Base URL (deployed) | `https://sobeet.onrender.com`                                                                                                    |
| Base URL (local)    | `http://127.0.0.1:8000` (see [Run locally](../README.md#9-run-locally))                                                          |
| Request bodies      | JSON, with the header `Content-Type: application/json`                                                                           |
| Login               | None in v1. Endpoints take ids in the URL or body.                                                                               |
| Ids                 | UUIDs, for example `9a6ebba0-00ba-4d07-9fda-c392b55090da`                                                                        |
| Times               | ISO 8601 with a UTC offset, for example `2026-11-03T09:00:00+03:00`. The clinic runs on `Africa/Nairobi` (UTC+03:00) by default. |
| Test clinic id      | `2b21687de8e644a8a8a6a3ab29128635`                                                                                               |

> **Creating a doctor on the public site? You must use the defined clinic id.**
> On `https://sobeet.onrender.com`, always send `"clinic_id": "2b21687de8e644a8a8a6a3ab29128635"` to `POST /doctors`. The API has no endpoint for creating clinics, so this is the clinic to use. An id that does not belong to a real clinic is rejected with `CLN001` (404) and no doctor is created.

The examples use `curl`. Set the base URL once in your terminal:

```bash
BASE=https://sobeet.onrender.com      # or http://127.0.0.1:8000
```

You can run every request instead from Swagger UI (`/docs`, then **Try it out**) or from the [Postman collection](https://www.postman.com/security-meteorologist-10250542-s-team/workspace/clinic-appointment-booking-system).

Dates in the examples are in November 2026. Bookings must be at least 61 minutes in the future, so use a future day on which the doctor works.

## The flow at a glance

```
1. Get doctors  -->  (none yet? create one with the clinic id)
2. Create a patient
3. Check the doctor's availability for a date
4. Book a slot
5. See the patient's appointments
6. Reschedule  and/or  7. Cancel
```

## 1. Get doctors

```bash
curl "$BASE/doctors"
```

Filter by clinic or status if you need to:

```bash
curl "$BASE/doctors?status=active"
curl "$BASE/doctors?clinic_id=2b21687de8e644a8a8a6a3ab29128635&status=adjunct"
```

Example response:

```json
[
  {
    "id": "9a6ebba0-00ba-4d07-9fda-c392b55090da",
    "email": "amina.wanjiru@sobeet.test",
    "full_name": "Amina Wanjiru",
    "phone_no": "+254711000001",
    "clinic_id": "2b21687d-e8e6-44a8-a8a6-a3ab29128635",
    "title": "Dr.",
    "speciality": "General Practice",
    "status": "active",
    "working_hours": [
      { "weekday": 2, "start_time": "08:00:00", "end_time": "17:00:00" },
      { "weekday": 3, "start_time": "08:00:00", "end_time": "17:00:00" }
    ]
  }
]
```

What to read from it:

- **`id`**: you need this for availability and booking.
- **`status`**: `inactive` doctors cannot be booked. `active` and `adjunct` can.
- **`working_hours`**: one block per working weekday. Weekdays run **Sunday = 1 to Saturday = 7**, so Monday is 2 and Friday is 6. A day with no block means the doctor does not work that day.

If the list is empty, create a doctor in the next section.

### Create a doctor

Every doctor belongs to a clinic, so the request must include `clinic_id`. **On the public site, `clinic_id` must be `2b21687de8e644a8a8a6a3ab29128635`.** Do not make up an id or reuse a doctor id or patient id here.

```bash
curl -X POST "$BASE/doctors" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "amina.wanjiru@sobeet.test",
    "full_name": "Amina Wanjiru",
    "clinic_id": "2b21687de8e644a8a8a6a3ab29128635",
    "phone_no": "+254711000001",
    "title": "Dr.",
    "speciality": "General Practice",
    "working_hours": [
      { "weekday": 2, "start_time": "08:00", "end_time": "17:00" },
      { "weekday": 3, "start_time": "08:00", "end_time": "17:00" },
      { "weekday": 4, "start_time": "08:00", "end_time": "17:00" },
      { "weekday": 5, "start_time": "08:00", "end_time": "17:00" },
      { "weekday": 6, "start_time": "08:00", "end_time": "17:00" }
    ]
  }'
```

The response is `201` with the same shape as one item in the list above. Copy the `id` as `<DOCTOR_ID>`.

| Field                             | Required | Notes                                                                                                                       |
| --------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
| `email`                           | Yes      | Must be unique across all accounts.                                                                                         |
| `full_name`                       | Yes      |                                                                                                                             |
| `clinic_id`                       | Yes      | The clinic the doctor works at. On the public site, always `2b21687de8e644a8a8a6a3ab29128635`.                              |
| `phone_no`, `title`, `speciality` | No       |                                                                                                                             |
| `status`                          | No       | `active` (default), `adjunct`, or `inactive`.                                                                               |
| `working_hours`                   | No       | One entry per weekday, each with `weekday`, `start_time`, `end_time` (`HH:MM`). Without hours the doctor has no free slots. |

Lunch is not part of the working hours. The clinic closes for lunch (12:30 to 13:30 by default), so give the doctor one block per day and do not split it.

Things that can go wrong:

| You sent                                                                                  | You get                                |
| ----------------------------------------------------------------------------------------- | -------------------------------------- |
| A `clinic_id` that does not exist (on the public site, any id other than the defined one) | `CLN001` (404)                         |
| An email that already has an account                                                      | `USR002` (409)                         |
| A missing field, bad status, bad weekday, or `end_time` not after `start_time`            | `GEN004` or a working-hours code (400) |

## 2. Create a patient

A patient is the person who books. Create one:

```bash
curl -X POST "$BASE/patients" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane.doe@example.com",
    "full_name": "Jane Doe",
    "phone_no": "+254700123456"
  }'
```

Response (`201`):

```json
{
  "id": "5d0f7c2e-4b1a-4c9e-8a3b-2f6e91d4c7a0",
  "email": "jane.doe@example.com",
  "full_name": "Jane Doe",
  "phone_no": "+254700123456"
}
```

Copy the `id` as `<PATIENT_ID>`. `phone_no` is optional. Using an email that is already registered returns `USR002` (409). To list patients: `curl "$BASE/patients"`.

For the later steps it helps to create a second patient (for example `john.doe@example.com`), so you can see what happens when two people want the same slot.

## 3. Check a doctor's availability

Pick a date and ask for that doctor's free slots:

```bash
curl "$BASE/doctors/<DOCTOR_ID>/availability?date=2026-11-03"
```

Example response (shortened):

```json
{
  "doctor_id": "9a6ebba0-00ba-4d07-9fda-c392b55090da",
  "date": "2026-11-03",
  "timezone": "Africa/Nairobi",
  "slots": [
    {
      "start_at": "2026-11-03T08:00:00+03:00",
      "end_at": "2026-11-03T08:30:00+03:00"
    },
    {
      "start_at": "2026-11-03T08:30:00+03:00",
      "end_at": "2026-11-03T09:00:00+03:00"
    },
    {
      "start_at": "2026-11-03T09:00:00+03:00",
      "end_at": "2026-11-03T09:30:00+03:00"
    },
    {
      "start_at": "2026-11-03T13:30:00+03:00",
      "end_at": "2026-11-03T14:00:00+03:00"
    }
  ]
}
```

How to read it:

- Every entry in `slots` is **free right now**. Slots are calculated on the fly, never stored.
- The list skips 12:30 to 13:30 because that is lunch.
- `start_at` already carries the clinic's offset. **Send it unchanged** when you book.

A slot is left out when any of these is true:

1. The doctor is `inactive`.
2. The date is a clinic holiday.
3. The doctor does not work that weekday, or the slot is outside their hours.
4. The slot is in the lunch window.
5. The doctor is on time off.
6. The slot is already booked.
7. The slot starts less than 61 minutes from now.

An empty `slots` list is a normal answer, not an error. The only errors here are `AVL001` (missing or badly formatted `date`, 400) and `DOC001` (unknown doctor, 404).

## 4. Book a slot

Take a `start_at` from the availability response:

```bash
curl -X POST "$BASE/appointments" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "<PATIENT_ID>",
    "doctor_id": "<DOCTOR_ID>",
    "start_at": "2026-11-03T09:00:00+03:00"
  }'
```

Response (`201`):

```json
{
  "id": "c7a1e0b4-6f2d-4a85-9b3c-0d5e8f1a2b34",
  "patient_id": "5d0f7c2e-4b1a-4c9e-8a3b-2f6e91d4c7a0",
  "doctor_id": "9a6ebba0-00ba-4d07-9fda-c392b55090da",
  "doctor_name": "Dr. Amina Wanjiru",
  "start_at": "2026-11-03T09:00:00+03:00",
  "end_at": "2026-11-03T09:30:00+03:00",
  "state": "booked",
  "cancelled_at": null,
  "cancel_reason": "",
  "rescheduled_from_id": null
}
```

Copy the `id` as `<APPOINTMENT_ID>`. You only send the start time. The end time is the start plus the clinic's slot length (30 minutes). Run the availability request again and 09:00 is gone.

### The booking logic

Every booking, and every reschedule target, goes through the same checks in the same order. The first rule broken is the error you get, so a request that breaks several rules always gets the same answer.

| Order | Check                                                                                   | Error                                  | HTTP |
| ----- | --------------------------------------------------------------------------------------- | -------------------------------------- | ---- |
| 1     | Body is a JSON object, required fields present, `start_at` is a valid timestamp         | `GEN001`, `GEN004`, `APT010`           | 400  |
| 2     | The doctor and the patient exist                                                        | `DOC001`, `PAT001`                     | 404  |
| 3     | The doctor is bookable (`active` or `adjunct`)                                          | `DOC002`                               | 422  |
| 4     | `start_at` is on a slot boundary (09:00 or 09:30, not 09:10)                            | `APT005`                               | 422  |
| 5     | Not in the past, then at least 61 minutes ahead                                         | `APT003`, `APT004`                     | 422  |
| 6     | Inside the doctor's working hours, outside lunch, not a clinic holiday, not in time off | `APT006`, `APT007`, `APT008`, `APT009` | 422  |
| 7     | The slot is free. If you already hold it, you are told so.                              | `APT002`, `APT015`                     | 409  |
| 8     | You have no other booked appointment that overlaps (even with a different doctor)       | `APT016`                               | 409  |

The slot rules in step 7 and 8 work like this:

- **Someone else holds the slot:** `APT002`, "slot already taken". Pick another slot.
- **You hold it yourself:** `APT015`, "you already hold this slot". You are not double-booked, just told the truth.
- **You are booked elsewhere at that time:** `APT016`. One person cannot be with two doctors at the same time. Back-to-back is fine: 09:00 to 09:30 with one doctor and 09:30 to 10:00 with another.

Two people booking the same slot at the same instant cannot both succeed. The database allows only one `booked` appointment per doctor and start time, so one request gets `201` and the other gets `APT002` (409).

Every error has the same JSON shape:

```json
{
  "error": "Dr. Amina Wanjiru is already booked at 2026-11-03 09:00. Please pick another slot. (Ref: APT002)",
  "code": "APT002",
  "message": "Slot already taken",
  "detail": "Dr. Amina Wanjiru is already booked at 2026-11-03 09:00. Please pick another slot."
}
```

Show `error` to a person. Branch on `code` in code, never on the text.

## 5. See a patient's appointments

```bash
curl "$BASE/patients/<PATIENT_ID>/appointments"
```

This returns the patient's **upcoming, `booked`** appointments, soonest first. Cancelled, rescheduled, and past appointments are not included. An unknown patient returns `PAT001` (404).

## 6. Reschedule

Move an appointment to another slot with the same doctor. Choose a free `start_at` from the availability response:

```bash
curl -X PATCH "$BASE/appointments/<APPOINTMENT_ID>/reschedule" \
  -H "Content-Type: application/json" \
  -d '{ "start_at": "2026-11-03T11:00:00+03:00" }'
```

What happens:

- The new time is checked exactly like a fresh booking (the table in step 4).
- The old appointment becomes `rescheduled` and its slot is free again.
- The response is a **new** appointment in state `booked`, with its own `id`. Its `rescheduled_from_id` points back to the old one. Use the **new** id for anything that follows.
- If the new slot fails any check, nothing changes and the original stays `booked`.

Extra errors for reschedule:

| Error          | Meaning                                                                   |
| -------------- | ------------------------------------------------------------------------- |
| `APT014` (422) | The new time is the same as the current one.                              |
| `APT011` (409) | The appointment is already cancelled.                                     |
| `APT012` (409) | The appointment is not `booked` (for example it was already rescheduled). |
| `APT001` (404) | No appointment with that id.                                              |

## 7. Cancel

A reason is required:

```bash
curl -X PATCH "$BASE/appointments/<APPOINTMENT_ID>/cancel" \
  -H "Content-Type: application/json" \
  -d '{ "reason": "Patient requested cancellation" }'
```

The response is the appointment with `state: "cancelled"`, `cancelled_at` set, and your `cancel_reason`. The slot is free again, so check availability and it reappears. Appointments are never deleted. They stay in the system as history.

| Error          | Meaning                       |
| -------------- | ----------------------------- |
| `APT013` (400) | No `reason`, or an empty one. |
| `APT011` (409) | Already cancelled.            |
| `APT012` (409) | Not in a `booked` state.      |
| `APT001` (404) | No appointment with that id.  |

## A full run-through to try

Use one doctor who works on your chosen day (call her **A**), and two patients (**P1** and **P2**). Pick a future date `D` on which A works.

| Step | Request                                                | Expected                                                          |
| ---- | ------------------------------------------------------ | ----------------------------------------------------------------- |
| 1    | `GET /doctors`                                         | A is listed with `working_hours`                                  |
| 2    | `POST /patients` for P1 and P2                         | `201` each                                                        |
| 3    | `GET /doctors/A/availability?date=D`                   | Slots from opening to closing, no lunch gap                       |
| 4    | P1 books A at 09:00                                    | `201`, state `booked`                                             |
| 5    | Availability again                                     | 09:00 is gone                                                     |
| 6    | P1 books A at 09:00 again                              | `APT015` (409)                                                    |
| 7    | P2 books A at 09:00                                    | `APT002` (409)                                                    |
| 8    | P1 books A at 09:30                                    | `201` (back-to-back is fine)                                      |
| 9    | A second doctor B also works on D. P1 books B at 09:30 | `APT016` (409)                                                    |
| 10   | P2 books A at 13:00                                    | `APT007` (422), lunch                                             |
| 11   | P2 books A on a Saturday or other non-working day      | `APT006` (422)                                                    |
| 12   | P2 books A at a past time                              | `APT003` (422)                                                    |
| 13   | P1 reschedules the 09:00 appointment to 11:00          | `200`, a new appointment with `rescheduled_from_id` set           |
| 14   | `GET /patients/P1/appointments`                        | Shows the 09:30 and the 11:00 appointments, not the old 09:00 one |
| 15   | P1 cancels the 11:00 appointment with a reason         | `200`, state `cancelled`                                          |
| 16   | Cancel it again                                        | `APT011` (409)                                                    |
| 17   | Cancel without a `reason`                              | `APT013` (400)                                                    |

Step 9 needs a second doctor. Create one with the defined clinic id (`2b21687de8e644a8a8a6a3ab29128635`) and working hours that cover your day.
