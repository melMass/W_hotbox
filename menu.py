import sys
from pathlib import Path

here = Path(__file__).parent
lib = here / "python"
sys.path.append(lib.as_posix())

from W_hotbox_lib import hotbox as W_hotbox

# NOTE: this is imported in the main thread
# making it accessible from commands.
from W_hotbox_lib import manager as W_hotboxManager

W_hotbox.register()

__all__ = ["W_hotbox", "W_hotboxManager"]
