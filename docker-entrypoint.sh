#!/bin/bash 
#!/bin/bash

# Start celery in the background
# start with 3 workers, scale up to 10 if necessary   
celery -A blackops.api.task worker -l info --concurrency=1 --loglevel info &

echo "Running CMD"
exec "$@"


