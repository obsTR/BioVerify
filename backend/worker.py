#!/usr/bin/env python
"""Celery worker entrypoint."""
from tasks.celery_app import celery_app

if __name__ == '__main__':
    celery_app.start()
