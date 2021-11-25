## Steps

select a symbol pair  

subscribe to the binance stream 

subscribe to the btcturk stream 

compare 

decide 

open order in btcturk 

follow order status 

cancel or wait for execution 

repeat 


---

docker run -d -p 7846:7846 -p 5555:5555 blackops    

docker build . -t blackops  

---

 worker: REMAP_SIGTERM=SIGQUIT celery  --app blackops.taskq.tasks.app worker -l info -c 1


---


 uvicorn blackops.api.main:app 
