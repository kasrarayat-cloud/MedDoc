#!/bin/sh
# CPT Studio container roles. Anything not listed here is refused.
#   web               gunicorn on 0.0.0.0:8000
#   worker            the DB-backed job worker
#   migrate           apply migrations, non-interactively
#   manage <cmd> ...  one Django management command
set -eu
cd /app

refuse() {
    echo "cpt-studio entrypoint: $1" >&2
    echo "usage: web | worker | migrate | manage <command> [args...]" >&2
    exit 64
}

[ "$(id -u)" != 0 ] || refuse "refusing to run as root."

role="${1:-}"
if [ "$#" -gt 0 ]; then shift; fi

case "$role" in
    web)
        [ "$#" -eq 0 ] || refuse "'web' takes no arguments."
        exec python -m gunicorn -c deploy/gunicorn.conf.py cptstudio.wsgi
        ;;
    worker)
        [ "$#" -eq 0 ] || refuse "'worker' takes no arguments."
        exec python manage.py run_worker
        ;;
    migrate)
        [ "$#" -eq 0 ] || refuse "'migrate' takes no arguments."
        exec python manage.py migrate --noinput
        ;;
    manage)
        [ "$#" -gt 0 ] || refuse "'manage' needs a management command."
        exec python manage.py "$@"
        ;;
    *)
        refuse "unknown role '${role}'."
        ;;
esac
