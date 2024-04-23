import sys
from pathlib import Path

here = Path(__file__).parent
lib = here / "python"
sys.path.append(lib.as_posix())

from W_hotbox_lib import hotbox
from W_hotbox_lib import manager as W_hotboxManager

hotbox.register()

__all__ = ["hotbox", "W_hotboxManager"]
