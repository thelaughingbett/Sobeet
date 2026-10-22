#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Install Chromium + system deps for Playwright
# playwright install --with-deps chromium 

python manage.py collectstatic --no-input
python manage.py migrate