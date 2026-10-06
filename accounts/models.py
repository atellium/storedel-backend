import uuid
import secrets
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from .managers import UserManager

phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Enter the phone number in international format, such as +919876543210.",
)

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True, validators=[phone_validator])
    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150, null=True, blank=True)

    username = None
    first_name = None
    last_name = None

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"

    def clean(self):
        super().clean()
        self.email = self.email.strip().lower() if self.email and self.email.strip() else None

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower() if self.email and self.email.strip() else None
        if self._state.adding and not self.password:
            self.set_unusable_password()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"
