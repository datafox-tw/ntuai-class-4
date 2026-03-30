#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python iceland_lab_web/app.py
