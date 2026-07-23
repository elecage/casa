"""Minimal example: load settings with an env override and enqueue a job."""

import os

os.environ["JOBQ_TIMEOUT_MS"] = "250"

from jobq.env import overrides           # noqa: E402
from jobq.settings import load           # noqa: E402

settings = load(overrides=overrides())
print("effective timeout_ms:", settings.timeout_ms)
