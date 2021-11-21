# @app.put(
#     "stg/run/",
#     tags=["run"],
# )
# async def run_stg(
#     stg: Strategy, background_tasks: BackgroundTasks, auth: bool = Depends(auth)
# ):

#     # stg = await get_stg(sha)

#     stg.is_valid()

#     stg_dict = dict(stg)

#     sha = dict_to_hash(stg_dict)

#     if sha in context.tasks:
#         raise Exception("Task already running o")

#     stg_dict["sha"] = sha

#     background_tasks.add_task(context.start_task, stg_dict)
#     return JSONResponse(content={"ok": f"task {sha} started with id {task_id}"})


# @app.put("/stop/all", tags=["stop"])
# async def stop_stg_all(auth: bool = Depends(auth)):
#     """
#     Stop all running tasks
#     """
#     await context.cancel_all()
#     return JSONResponse(content={"message": f"stopped all"})


# @app.put("/stop/{sha}", tags=["stop"])
# async def stop_stg(sha: str, auth: bool = Depends(auth)):
#     """
#     Copy and paste the sha from the response of run_stg to stop the task.
#     """
#     await context.cancel_task(sha)
#     return JSONResponse(content={"message": f"stopped task {sha}"})


# @app.get("/orders/{sha}", tags=["order history"])
# async def order_history(sha: str, auth: bool = Depends(auth)):
#     """ """
#     orders = context.get_orders(sha)
#     return JSONResponse(content={"sha": sha, "history": orders})
