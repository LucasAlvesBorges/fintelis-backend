import uuid
from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email=None, first_name=None, last_name=None, password=None, **extra_fields):
        """
        Cria um usuário. Para usuários PLATAFORMA, email e password são obrigatórios.
        Para usuários OPERADOR, apenas first_name e last_name são obrigatórios.
        """
        user_type = extra_fields.get("user_type", User.UserType.PLATAFORMA)
        
        if not first_name:
            raise ValueError("Users must have a first name")
        if not last_name:
            raise ValueError("Users must have a last name")
        
        # Usuários da plataforma precisam de email
        if user_type == User.UserType.PLATAFORMA:
            if not email:
                raise ValueError("Usuários da plataforma precisam de um email")
            email = self.normalize_email(email)
        else:
            # Usuários operadores não precisam de email único
            # Geramos um email placeholder único se não fornecido
            if not email:
                email = f"operador_{uuid.uuid4().hex[:8]}@operador.local"
            else:
                email = self.normalize_email(email)

        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            **extra_fields,
        )
        
        # Apenas usuários da plataforma têm senha
        if user_type == User.UserType.PLATAFORMA and password:
            user.set_password(password)
        else:
            user.set_unusable_password()
            
        user.save(using=self._db)
        return user

    def create_operator(self, first_name, last_name, company=None, **extra_fields):
        """
        Cria um usuário operador (sem login, apenas para histórico de vendas).
        """
        extra_fields["user_type"] = User.UserType.OPERADOR
        extra_fields["is_active"] = True
        if company:
            extra_fields["operator_company"] = company
        return self.create_user(
            email=None,
            first_name=first_name,
            last_name=last_name,
            password=None,
            **extra_fields
        )

    def create_superuser(
        self, email, first_name, last_name, password=None, **extra_fields
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("user_type", User.UserType.PLATAFORMA)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        user = self.create_user(email, first_name, last_name, password, **extra_fields)

        user.save(using=self._db)
        return user


name_validator = RegexValidator(
    regex=r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?: [A-Za-zÀ-ÖØ-öø-ÿ]+)*$",
    message="Use apenas letras e espaços (sem números ou caracteres especiais).",
)


def default_trial_end():
    return timezone.now() + timedelta(days=15)


class User(AbstractBaseUser, PermissionsMixin):

    class UserType(models.TextChoices):
        PLATAFORMA = "plataforma", "Usuário da Plataforma"
        OPERADOR = "operador", "Usuário Operador"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.PLATAFORMA,
        help_text="Tipo de usuário: PLATAFORMA (com login) ou OPERADOR (apenas histórico)"
    )
    first_name = models.CharField(max_length=150, validators=[name_validator])
    last_name = models.CharField(max_length=150, validators=[name_validator])
    email = models.EmailField(max_length=255, unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Campo para associar operadores a uma empresa específica
    operator_company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="operators",
        help_text="Empresa à qual o operador pertence (apenas para usuários OPERADOR)"
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "user"
        ordering = ["id"]

    def __str__(self):
        if self.user_type == self.UserType.OPERADOR:
            return f"{self.first_name} {self.last_name} (Operador)"
        return self.email
    
    @property
    def is_platform_user(self):
        """Retorna True se o usuário é da plataforma (com login)"""
        return self.user_type == self.UserType.PLATAFORMA
    
    @property
    def is_operator(self):
        """Retorna True se o usuário é operador (sem login)"""
        return self.user_type == self.UserType.OPERADOR
    
    @property
    def full_name(self):
        """Retorna o nome completo do usuário"""
        return f"{self.first_name} {self.last_name}"

