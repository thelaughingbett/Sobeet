## Data model

### Entity relationship diagram

```mermaid
erDiagram

    Account {
        uuid id PK
        string email UK
        string password_hash
        enum role "patient, doctor, admin"
        string full_name
        string phone_no
    }

    Clinic {
        uuid id PK
        string name
        string timezone "IANA name, e.g. Africa/Nairobi"
        int slot_minutes
        time lunch_start
        time lunch_end
    }

    ClinicHoliday {
        uuid id PK
        uuid clinic_id FK
        date holiday_date
        string name
        boolean is_yearly "if true, match on month and day only"
    }

    Doctor {
        uuid id PK
        uuid account_id FK
        uuid clinic_id FK
        string title
        string speciality
        enum status "inactive, active, adjunct"
    }

    WorkingHours {
        uuid id PK
        uuid doctor_id FK
        int weekday "Sunday = 1 ... Saturday = 7"
        time start_time
        time end_time
    }

    TimeOff {
        uuid id PK
        uuid doctor_id FK
        timestamptz start_at
        timestamptz end_at
        enum reason "leave, sick, conference, other"
        string note
    }

    Patient {
        uuid id PK
        uuid account_id FK
    }

    Appointment {
        uuid id PK
        uuid patient_id FK
        uuid doctor_id FK
        timestamptz start_at
        timestamptz end_at
        enum state "booked, cancelled, executed, rescheduled, no_show"
        timestamptz cancelled_at "nullable"
        uuid rescheduled_from_id FK "nullable, self reference"
    }

    Chart {
        uuid id PK
        uuid patient_id FK
    }

    %% ---------- Relations ----------
    Account ||--o| Doctor : "is"
    Account ||--o| Patient : "is"
    Clinic ||--o{ Doctor : employs
    Clinic ||--o{ ClinicHoliday : observes
    Doctor ||--o{ WorkingHours : has
    Doctor ||--o{ TimeOff : takes
    Doctor ||--o{ Appointment : receives
    Patient ||--o{ Appointment : books
    Patient ||--o{ Chart : has
    Appointment |o--o| Appointment : "rescheduled from"
```

### Enums

**Doctor.status**

| Value      | Meaning                                  | Bookable? |
| ---------- | ---------------------------------------- | --------- |
| `active`   | Regular doctor                           | Yes       |
| `adjunct`  | Part-time or visiting doctor             | Yes       |
| `inactive` | Left the clinic or long-term unavailable | No        |

**Appointment.state**

| Value         | Meaning                                            | Holds the slot?        |
| ------------- | -------------------------------------------------- | ---------------------- |
| `booked`      | Confirmed, upcoming                                | **Yes**                |
| `cancelled`   | Cancelled, no replacement                          | No                     |
| `rescheduled` | Moved; a newer appointment points back to this one | No                     |
| `executed`    | The visit took place                               | No (it is in the past) |
| `no_show`     | The patient did not attend                         | No (it is in the past) |

`cancelled` and `rescheduled` are deliberately separate states. Both release the slot, but keeping them apart lets us answer questions such as "how many appointments did patients abandon versus move?" without guessing.

State transitions:

```
booked -> cancelled
booked -> rescheduled
booked -> executed
booked -> no_show
```

All other states are terminal.
