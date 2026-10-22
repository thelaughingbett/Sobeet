# AI Reflection

This document covers my use of Claude (Anthropic's chat assistant) on this project. Claude worked only in the chat. It had no access to my repository and never ran any code, so everything it produced was copied into the project and run by me. That matters for the answers below.

## 1. What did I use AI for?

- **Design.** I pasted the clinic requirements and my first ER diagram and asked for a review. I then used it to test my own ideas: whether lunch and holidays could be clinic-wide settings, and whether an enum on the doctor could replace a time-off table. It drafted the `TimeOff` model once I decided to keep one.
- **Documentation.** The first draft of the README (models, components, key decisions, trade-offs), the endpoint and validation section after I corrected the endpoints to the brief, and `docs/ERROR_CODES.md`.
- **Code.**
  - The error module (`base/errors.py`), adapted from a pattern I pasted from another project.
  - The models, one file per model.
  - The services: availability, slot validation, booking, cancel and reschedule.
  - The Django REST Framework views, the output serializer and the URL routes.
- **Tests.** The unit tests for the booking logic and the endpoint tests (93 tests in total).
- **CI.** The GitHub Actions workflow, adapted from GitHub's default Django template to my `dev` and `prod` branches.
- **Debugging.** Reading tracebacks and explaining them.

This document only covers what I used Claude for in the chat.

## 2. An example where an AI suggestion improved my work

**What I prompted it with:** the clinic problem statement ("small clinic with 5 doctors, patients book online, a booked slot must not be available to others, patients can cancel") plus my first ER diagram, with `days` as a string on `Doctor`, `Time` fields on `Appointment`, and no rule for double booking.

**What improved:**

- **Slots are computed, not stored.** There is no `Slot` table. This removed a whole category of "slot rows out of sync with working hours" bugs.
- **Double booking is stopped by the database.** I had been thinking of checking availability in code and then inserting. Claude pointed out the race condition, where two patients pass the check at the same moment, and suggested a constraint on booked appointments. The constraint ignores `cancelled` and `rescheduled` rows, so history is kept without blocking rebooking. My tests now insert duplicates directly to prove the database rejects them.
- **Smaller fixes:** one `WorkingHours` row per weekday instead of a `days` string, and timestamps with a timezone instead of bare times.

## 3. An example where AI output was wrong or incomplete

**The test helper bug.** Claude wrote the endpoint tests with a helper `payload(self, start_at, **overrides)` and a test that called `payload(..., start_at=value)` to send bad timestamps. That raises `TypeError: got multiple values for argument 'start_at'`.

**How I caught it:** I ran `manage.py test`. Of 93 tests, 90 passed and 3 errored, all from that one test. Claude could not have caught it because it never ran the suite. The fix was renaming the helper's argument.

**The same run exposed a second problem:** the suite took almost 10 minutes. The test fixtures called `create_user` with a password, which triggers Django's deliberately slow password hashing for every account in every test. I passed `password=None` so no hashing happens.

**Other things Claude got wrong or left incomplete, all caught by running the code:**

- It generated a Postgres-only `ExclusionConstraint` for the double-booking rule. I develop on SQLite, so `makemigrations` crashed with `ModuleNotFoundError: psycopg`. I replaced it with a partial unique constraint. The trade-off is that it only catches identical start times, which is documented as a limitation in the README.

**What I take from this:** AI-written code needs to be run, not just read. Every one of these was found by executing it, not by reviewing it.

## 4. Two decisions I made without AI

1. **Lunch and holidays are clinic-wide settings.** I proposed this myself: the time-off policy applies to the whole clinic, with lunch as one window and holidays as a flat list. I also added the `is_yearly` flag on holidays so fixed-date holidays do not need re-entering every year. I trusted my judgment because this is a rule about how this clinic runs, and I know that better than a model could. Claude evaluated the idea and listed trade-offs (no per-doctor absences, a single lunch window), but the decision was mine. I kept a separate per-doctor `TimeOff` table for absences that really are personal.
2. **Keeping `rescheduled` and `cancelled` as separate states, and auto-rescheduling on time off without notifications.** Claude had suggested modelling a reschedule as a cancellation with a link back. I chose separate states for auditability, so I can later report on appointments patients abandoned versus ones that were moved. I also decided that, for now, affected appointments should be moved automatically and notifications left out. I trusted my judgment because both are product-scope decisions: what the clinic needs first and what is worth building in a first version. The trade-offs are written down in the README (section 8).
