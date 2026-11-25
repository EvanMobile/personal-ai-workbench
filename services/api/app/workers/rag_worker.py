"""Independent RAG Lab worker process.

Run with::

    cd services/api
    .venv/bin/python -m app.workers.rag_worker
"""

from __future__ import annotations

import logging
import os

from app.modules.evaluation.handlers.dossier_rollup import dossier_rollup
from app.modules.execution.config import ExecutionConfig
from app.modules.execution.worker import Worker


def build_handlers() -> dict:
    handlers = {"dossier_rollup": dossier_rollup}
    if os.getenv("RAG_WORKER_TEST_HANDLERS", "").strip().lower() in {"1", "true", "yes", "on"}:
        from app.workers.test_handlers import HANDLERS as TEST_HANDLERS

        handlers.update(TEST_HANDLERS)
    return handlers


def main() -> None:
    logging.basicConfig(
        level=os.getenv("RAG_WORKER_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = ExecutionConfig.from_env()
    worker = Worker(config=config, handlers=build_handlers())
    worker.run_forever()


if __name__ == "__main__":
    main()
