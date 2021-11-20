#!/bin/bash 

celery -A blackops.taskq.tasks worker -l info

celery  --broker=redis://localhost:6379/0 flower --port=5566

echo "Running CMD"
exec "$@"


