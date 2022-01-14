from dataclasses import dataclass
from typing import List

import src.pubsub.log_pub as log_pub
from src.flow.runner import flow_runner
from src.monitoring import logger
from src.stgs import StrategyConfig


@dataclass
class FlowApi:
    @staticmethod
    def is_running(sha: str):
        if flow_runner.is_running(sha):
            raise Exception(f"{sha} already running")

    @staticmethod
    async def run_task(stg: StrategyConfig):
        FlowApi.is_running(stg.sha)
        await flow_runner.start_flow(stg)

    async def stop_task(self, sha: str):
        await flow_runner.clean_task(sha)
        msg = f"{sha} stopped"
        logger.info(msg)
        log_pub.publish_message(message=msg)
        return sha

    async def stop_all_tasks(self) -> List[str]:
        stopped_shas = []
        shas = list(flow_runner.flowruns.keys())
        for sha in shas:
            try:
                await self.stop_task(sha)
                stopped_shas.append(sha)
            except Exception as e:
                msg = f"{sha} failed to stop: {e}"
                logger.error(msg)
                log_pub.publish_message(message=msg)

        msg = f"{stopped_shas} stopped"
        logger.info(msg)
        log_pub.publish_message(message=msg)
        return stopped_shas

    def get_tasks(self) -> List[str]:
        return flow_runner.get_tasks()


flow_api = FlowApi()
