"""AAL import helper.

``awesome_actus_lib`` is a required project dependency. This helper keeps the
single import point used by the AAL asset engine and diagnostic scripts.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import awesome_actus_lib


def get_aal_module() -> ModuleType | Any:
    """Return the required Awesome ACTUS Library module."""
    return awesome_actus_lib
