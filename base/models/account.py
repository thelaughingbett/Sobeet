from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

from .base import BaseModel


class AccountManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")

        email = self.normalize_email(email).lower()
        account = self.model(email=email, **extra)
        account.set_password(password)
        account.save(using=self._db)
        return account

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Account.Role.ADMIN)
        return self._create(email, password, **extra)


class Account(BaseModel, AbstractBaseUser, PermissionsMixin):
    """Login identity. Doctor and Patient are profiles attached to an Account."""

    class Role(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone_no = models.CharField(max_length=32, blank=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.PATIENT
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = AccountManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"
