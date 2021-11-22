web: uvicorn blackops.api.main:app --host=0.0.0.0 --port=$PORT --workers 1 --reload 

worker: REMAP_SIGTERM=SIGQUIT celery  --app blackops.taskq.tasks.app worker -l info -c 1