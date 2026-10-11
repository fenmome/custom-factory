#!/usr/bin/env bash
set -euo pipefail

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<'SQL'
CREATE DATABASE IF NOT EXISTS custom_factory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON custom_factory.* TO 'cf_user'@'%';
FLUSH PRIVILEGES;
SQL
