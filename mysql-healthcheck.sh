#!/bin/bash
set -eo pipefail

if [ -n "${MYSQL_ROOT_PASSWORD:-}" ] && [ -z "${MYSQL_USER:-}" ] && [ -z "${MYSQL_PASSWORD:-}" ]; then
  echo >&2 'Healthcheck error: cannot determine root password (and MYSQL_USER and MYSQL_PASSWORD were not set)'
  exit 0
fi

host="$(hostname --ip-address 2>/dev/null || echo '127.0.0.1')"
user="${MYSQL_USER:-root}"
export MYSQL_PWD="${MYSQL_PASSWORD:-$MYSQL_ROOT_PASSWORD}"

args=(
  -h"$host"
  -u"$user"
  --silent
)

STATUS=0
if command -v mysqladmin &>/dev/null; then
  if mysqladmin "${args[@]}" ping 2>/dev/null; then
    database_check=$(mysql -u"$user" -D oai_db --silent -e "SELECT 1 FROM users LIMIT 1;" 2>/dev/null) || true
    if [ -z "$database_check" ]; then
      echo "Healthcheck error: oai_db not populated"
      STATUS=1
    fi
  else
    echo "Healthcheck error: Mysql port inactive"
    STATUS=1
  fi
else
  if select=$(echo 'SELECT 1' | mysql "${args[@]}" 2>/dev/null) && [ "$select" = '1' ]; then
    database_check=$(mysql -u"$user" -D oai_db --silent -e "SELECT 1 FROM users LIMIT 1;" 2>/dev/null) || true
    if [ -z "$database_check" ]; then
      echo "Healthcheck error: oai_db not populated"
      STATUS=1
    fi
  else
    echo "Healthcheck error: Mysql port inactive"
    STATUS=1
  fi
fi
exit $STATUS
