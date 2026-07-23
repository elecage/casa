"""Minimal example: load settings with an env override and enqueue a job."""

import os

os.environ["JOBQ_DEADLINE_MS"] = "250"

from jobq.env import overrides           # noqa: E402
from jobq.settings import load           # noqa: E402

settings = load(overrides=overrides())
print("effective deadline_ms:", settings.deadline_ms)
