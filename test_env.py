import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if API key is available
api_key = os.getenv("EXTERNAL_API_KEY")
if api_key:
    print(f"API key found: {api_key[:5]}...{api_key[-5:]}")
else:
    print("ERROR: EXTERNAL_API_KEY not found in environment variables")

# List all environment variables
print("\nAll environment variables:")
for key, value in os.environ.items():
    if key.startswith("EXTERNAL_"):
        masked_value = f"{value[:5]}...{value[-5:]}" if value else "None"
        print(f"{key}={masked_value}")