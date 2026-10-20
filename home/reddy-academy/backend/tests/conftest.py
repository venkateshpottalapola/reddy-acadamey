import sys
import os

# Ensure the backend directory is on sys.path so `app` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
