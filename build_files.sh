#!/bin/bash
echo "Building project packages..."
# Vercel uses uv by default for new Python projects. We'll use uv to sync dependencies.
uv sync

echo "Collect Static..."
python manage.py collectstatic --noinput --clear

echo "Run Migrations..."
python manage.py migrate --noinput
