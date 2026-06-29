import os
from dotenv import load_dotenv
load_dotenv(r"E:\MiroFish\.env", override=True)

zep_key = os.environ.get("ZEP_API_KEY")
print(f"Key length: {len(zep_key)}")
print(f"Key start: {zep_key[:30]}")

from zep_cloud.client import Zep

# Check Zep client init parameters
import inspect
sig = inspect.signature(Zep.__init__)
print(f"\nZep.__init__ parameters: {list(sig.parameters.keys())}")

# Try creating client
client = Zep(api_key=zep_key)
print(f"\nClient created successfully")
print(f"Client type: {type(client)}")

# Check if there's a base_url or similar
if hasattr(client, 'base_url'):
    print(f"Base URL: {client.base_url}")
if hasattr(client, '_client'):
    print(f"Inner client: {type(client._client)}")
