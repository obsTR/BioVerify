#!/bin/bash
# Initialize MinIO bucket for bioverify

until mc alias set local http://localhost:9000 minioadmin minioadmin; do
  echo "Waiting for MinIO..."
  sleep 2
done

mc mb local/bioverify --ignore-existing
echo "MinIO bucket 'bioverify' created"
