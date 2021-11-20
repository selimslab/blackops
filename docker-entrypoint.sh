#!/bin/bash 

# celery -A blackops.taskq.tasks worker -l info

# celery  --broker=redis://localhost:6379/0 flower --port=5566

celery  --broker=$REDIS_HOST -A blackops.taskq.tasks worker -l info

echo "Running CMD"
exec "$@"


