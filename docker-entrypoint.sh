#!/bin/bash 
#!/bin/bash

# Start celery in the background
# start with 3 workers, scale up to 10 if necessary   
celery flower -A blackops.taskq.tasks worker -l info --concurrency=1 --loglevel info --logfile=/var/log/celery/flower.log --pidfile=/var/run/celery/flower.pid 

echo "Running CMD"
exec "$@"


