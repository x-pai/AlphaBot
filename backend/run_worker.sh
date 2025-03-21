#!/bin/bash

echo "启动Celery worker..."
cd "$(dirname "$0")"
celery -A app.core.celery_app:celery_app worker -l info -Q ai_tasks 