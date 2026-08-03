#!/bin/sh
set -e

exec ./node_modules/.bin/next start -p "${PORT:-3000}"
