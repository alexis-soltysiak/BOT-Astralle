from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_params() -> dict:
    p = os.environ.get("SCORING_PARAMS_PATH")
    if p:
        path = Path(p)
    else:
        path = Path(__file__).with_name("params_v1.json")
    return json.loads(path.read_text(encoding="utf-8"))