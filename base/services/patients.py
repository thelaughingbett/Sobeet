from django.db import transaction

from base.models import Account, Patient
from base.utils.errors import GEN004


@transaction.atomic
def create_patient(*, email, full_name, phone_no=""):
    email = email.strip().lower()
    if Account.objects.filter(email=email).exists():
        # Swap in whichever ClinicError you use for conflicts (e.g. a PAT code, 409).
        raise GEN004(detail="An account with this email already exists.")

    account = Account.objects.create_user(
        email=email,
        password=None,  # unusable password; auth isn't wired in yet
        full_name=full_name,
        phone_no=phone_no,
        role=Account.Role.PATIENT,
    )
    return Patient.objects.create(account=account)


def list_patients():
    return Patient.objects.select_related("account").order_by("account__full_name")
