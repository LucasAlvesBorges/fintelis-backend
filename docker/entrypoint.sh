#!/bin/sh

set -e

should_run_migrations() {
    case "$(printf '%s' "${RUN_MIGRATIONS:-true}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

if should_run_migrations; then
    python manage.py migrate --noinput
fi

exec "$@"
