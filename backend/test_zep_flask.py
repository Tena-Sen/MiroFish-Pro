import os
import sys
sys.path.insert(0, r"E:\MiroFish\backend")

from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

# Simulate Flask environment
os.environ["FLASK_APP"] = "run.py"

from app.config import Config
from app.services.graph_builder import GraphBuilderService

print(f"Config key: {Config.ZEP_API_KEY[:30]}...")

builder = GraphBuilderService()
print(f"Builder key: {builder.api_key[:30]}...")

try:
    graph_id = builder.create_graph(name="test_from_flask")
    print(f"SUCCESS: {graph_id}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)[:300]}")
