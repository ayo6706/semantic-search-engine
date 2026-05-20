import sys
from unittest.mock import MagicMock

# Mock sentence_transformers to avoid importing PyTorch
# which has a broken DLL initialization on this system.
sys.modules['sentence_transformers'] = MagicMock()
