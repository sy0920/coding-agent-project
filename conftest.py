"""确保仓库根目录在 sys.path 上，便于 `import coding_agent` 与 `import tests`。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
