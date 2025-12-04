import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Tentar carregar variáveis do arquivo .env se python-dotenv estiver disponível
try:
    from dotenv import load_dotenv
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Arquivo .env carregado de: {env_path}")
    else:
        print(f"⚠️  Arquivo .env não encontrado em: {env_path}")
except ImportError:
    print("⚠️  python-dotenv não instalado. Instale com: pip install python-dotenv")
    print("   Ou configure as variáveis de ambiente diretamente no sistema/Docker.")
except Exception as e:
    print(f"⚠️  Erro ao carregar .env: {e}")


def get_bool_env(var_name: str, default: bool = False) -> bool:
    value = os.environ.get(var_name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")

DEBUG = get_bool_env("DJANGO_DEBUG")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

# Em desenvolvimento, permite qualquer domínio ngrok dinamicamente via middleware
# O middleware NgrokHostMiddleware adiciona domínios ngrok ao ALLOWED_HOSTS em tempo de execução


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "apps.users",
    "apps.companies",
    "apps.contacts",
    "apps.financials",
    "apps.inventory",
    "apps.dashboards",
    "apps.notifications",
    "apps.payments",
    "rest_framework",
    "django_celery_beat",
]

MIDDLEWARE = [
    "fintelis.middleware.NgrokHostMiddleware",  # Permite domínios ngrok em desenvolvimento (deve vir antes do SecurityMiddleware)
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fintelis.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "fintelis.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME") or os.environ.get("POSTGRES_DB", "fintelis"),
        "USER": os.environ.get("DB_USER")
        or os.environ.get("POSTGRES_USER", "fintelis"),
        "PASSWORD": os.environ.get("DB_PASSWORD")
        or os.environ.get("POSTGRES_PASSWORD", "fintelis"),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT") or os.environ.get("POSTGRES_PORT", "5432"),
    }
}


REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.users.authentication.CompanyJWTAuthentication",
        "apps.users.authentication.CookieJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

if not DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
        "rest_framework.renderers.JSONRenderer",
    ]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_REFRESH": "refresh_token",
    "AUTH_COOKIE_SECURE": False,
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
    # Company-bound token settings: issued by /api/v1/users/company-token/,
    # sent via header X-Company-Token or cookie company_access_token.
    "COMPANY_ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "COMPANY_AUTH_COOKIE": "company_access_token",
}

AUTH_USER_MODEL = "users.User"

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE")
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Mercado Pago Configuration
MERCADOPAGO_ACCESS_TOKEN = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
MERCADOPAGO_PUBLIC_KEY = os.environ.get("MERCADOPAGO_PUBLIC_KEY")

# Debug: Imprimir variáveis de ambiente importantes
print("\n" + "="*80)
print("🔍 DEBUG: Variáveis de Ambiente")
print("="*80)
print(f"DEBUG: {DEBUG}")
print(f"ALLOWED_HOSTS: {ALLOWED_HOSTS}")
print(f"CORS_ALLOWED_ORIGINS: {CORS_ALLOWED_ORIGINS}")
print(f"MERCADOPAGO_ACCESS_TOKEN: {'✅ Configurado' if MERCADOPAGO_ACCESS_TOKEN else '❌ NÃO CONFIGURADO'}")
if MERCADOPAGO_ACCESS_TOKEN:
    # Mostrar apenas os primeiros e últimos caracteres por segurança
    token_preview = MERCADOPAGO_ACCESS_TOKEN[:10] + "..." + MERCADOPAGO_ACCESS_TOKEN[-10:] if len(MERCADOPAGO_ACCESS_TOKEN) > 20 else "***"
    print(f"  Token preview: {token_preview}")
print(f"MERCADOPAGO_PUBLIC_KEY: {'✅ Configurado' if MERCADOPAGO_PUBLIC_KEY else '❌ NÃO CONFIGURADO'}")
print(f"DB_HOST: {os.environ.get('DB_HOST', 'NÃO CONFIGURADO')}")
print(f"DB_NAME: {os.environ.get('DB_NAME') or os.environ.get('POSTGRES_DB', 'NÃO CONFIGURADO')}")
print("="*80 + "\n")

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


STATIC_URL = "static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


print(CORS_ALLOWED_ORIGINS)
