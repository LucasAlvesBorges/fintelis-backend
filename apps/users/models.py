import uuid
from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        if not first_name:
            raise ValueError('Users must have a first name')
        if not last_name:
            raise ValueError('Users must have a last name')

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        user = self.create_user(email, first_name, last_name, password, **extra_fields)
        user.subscription_active = True
        user.subscription_expires_at = None
        user.save(using=self._db)
        return user


name_validator = RegexValidator(
    regex=r'^[A-Za-zÀ-ÖØ-öø-ÿ]+(?: [A-Za-zÀ-ÖØ-öø-ÿ]+)*$',
    message='Use apenas letras e espaços (sem números ou caracteres especiais).',
)


def default_trial_end():
    return timezone.now() + timedelta(days=15)


class User(AbstractBaseUser, PermissionsMixin):
    class SubscriptionPlan(models.TextChoices):
        MONTHLY = 'monthly', 'Mensal (R$500 via Pix)'
        QUARTERLY = 'quarterly', 'Trimestral (R$1500 via Pix)'
        SEMIANNUAL = 'semiannual', 'Semestral (R$ 3000 via Pix)'
        ANNUAL = 'annual', 'Anual (R$6000 via Pix)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=150, validators=[name_validator])
    last_name = models.CharField(max_length=150, validators=[name_validator])
    email = models.EmailField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_active = models.BooleanField(default=False)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        null=True,
        blank=True,
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'user'
        ordering = ['id']

    def __str__(self):
        return self.email

    @property
    def has_active_access(self) -> bool:
        """
        Allows login if trial is still valid or there is an active subscription.
        """
        now = timezone.now()
        if self.trial_ends_at and now <= self.trial_ends_at:
            return True
        if self.subscription_active:
            if self.subscription_expires_at:
                return now <= self.subscription_expires_at
            return True
        return False

    def start_trial(self):
        self.trial_ends_at = default_trial_end()
        self.save(update_fields=['trial_ends_at'])
