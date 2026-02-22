#!/usr/bin/env python
"""Check if Celery worker is running and can receive tasks."""
import os
import sys
from celery import Celery

broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')

app = Celery('test')
app.conf.broker_url = broker_url

# Test connection
try:
    inspect = app.control.inspect()
    active_workers = inspect.active()
    if active_workers:
        print("✓ Worker is running!")
        print(f"Active workers: {list(active_workers.keys())}")
    else:
        print("✗ No active workers found")
        print("Make sure the worker container is running: docker-compose up -d worker")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error connecting to broker: {e}")
    print(f"Broker URL: {broker_url}")
    sys.exit(1)
