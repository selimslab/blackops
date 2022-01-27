from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

process_pool_executor = ProcessPoolExecutor(max_workers=2)

thread_pool_executor = ThreadPoolExecutor()
