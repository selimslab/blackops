#!/bin/bash 
#!/bin/bash

# Start celery in the background
# start with 3 workers, scale up to 10 if necessary   
celery  -A blackops.taskq.taskq worker -l info --concurrency=1 --loglevel info --logfile=/var/log/celery/flower.log --pidfile=/var/run/celery/flower.pid flower --address=0.0.0.0 --port=5566

echo "Running CMD"
exec "$@"


