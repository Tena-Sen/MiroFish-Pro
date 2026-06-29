import os
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")
print(f"Testing ZEP SDK directly...")

from zep_cloud.client import Zep

try:
    client = Zep(api_key=zep_key)
    print("Client created OK")
    
    # Try to list graphs
    result = client.graph.create(name="test")
    print(f"Success: {result}")
except Exception as e:
    print(f"Error type: {type(e).__name__}")
    print(f"Error: {str(e)[:500]}")
