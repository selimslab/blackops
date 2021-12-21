import time
from datetime import datetime

t = time.time()

dt = datetime.fromtimestamp(t / 1000)

print(t, dt)
