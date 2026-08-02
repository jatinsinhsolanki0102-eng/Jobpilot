#!/bin/sh
set -e

exec next start -p "${PORT:-3000}"
