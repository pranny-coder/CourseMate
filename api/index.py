import os
import sys

# Add parent directory to sys.path so app modules can be resolved
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
