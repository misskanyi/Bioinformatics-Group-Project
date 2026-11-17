"""In-memory bulk-analysis jobs.

Uploaded sequences live only in this process's memory and are dropped when a
job expires (JOB_TTL), is deleted, or the server restarts; nothing is written
to disk. One worker thread processes jobs in order so a large batch cannot
starve the rest of the API.
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List

from pet_explorer.batch import Record

JOB_TTL = 60 * 60
MAX_JOBS = 20

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="batch")
_jobs: Dict[str, "Job"] = {}
_lock = threading.Lock()


class Job:
    def __init__(self, records: List[Record], meta: dict):
        self.id = uuid.uuid4().hex
        self.created = time.time()
        self.records = records
        self.meta = meta
        self.results: List[dict] = []
        self.state = "queued"          # queued | running | done | cancelled
        self.cancelled = False

    def view(self, since: int = 0) -> dict:
        return {"job_id": self.id, "state": self.state, "total": len(self.records), "done": len(self.results),
                "results": self.results[since:], "meta": self.meta}


def _prune():
    now = time.time()
    for jid in [j for j, job in _jobs.items() if now - job.created > JOB_TTL]:
        _jobs.pop(jid).cancelled = True
    while len(_jobs) >= MAX_JOBS:
        _jobs.pop(next(iter(_jobs))).cancelled = True


def submit(records: List[Record], meta: dict, analyse: Callable[[Record], dict]) -> Job:
    """Queue a job. `analyse(record)` returns the result row for a valid record (and may raise)."""
    job = Job(records, meta)
    with _lock:
        _prune()
        _jobs[job.id] = job

    def run():
        job.state = "running"
        by_row: Dict[int, dict] = {}
        for rec in job.records:
            if job.cancelled:
                job.state = "cancelled"
                return
            if rec.status == "valid":
                try:
                    row = analyse(rec)
                except Exception as e:  # one failing sequence must not stop the batch
                    row = {"status": "error", "errors": [f"Analysis failed: {e}"]}
            elif rec.status == "duplicate":
                original = by_row.get(rec.duplicate_of, {})
                row = {**original, "status": "duplicate",
                       "errors": [], "warnings": [f"Same sequence as record {rec.duplicate_of}; results copied."]}
            else:
                row = {"status": "invalid"}
            row = {**row, **{k: v for k, v in rec.summary().items() if k not in ("status", "preview")},
                   "status": row.get("status", "analysed"),
                   "errors": rec.errors + row.get("errors", []),
                   "warnings": rec.warnings + row.get("warnings", [])}
            by_row[rec.row] = row
            job.results.append(row)
        job.state = "done"

    _executor.submit(run)
    return job


def get(job_id: str):
    with _lock:
        _prune()
        return _jobs.get(job_id)


def delete(job_id: str) -> bool:
    with _lock:
        job = _jobs.pop(job_id, None)
    if job:
        job.cancelled = True
    return job is not None
