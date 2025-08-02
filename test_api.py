import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key and URL
api_key = os.getenv("EXTERNAL_API_KEY")
base_url = os.getenv("EXTERNAL_API_URL", "https://www.tickertalk.in")
url = f"{base_url}/api/external/bulk-upload-posts-comments"

print(f"API Key: {api_key}")
print(f"URL: {url}")

# Create test payload
payload = {
    "posts": [
        {
            "temp_post_id": "test_001",
            "title": "Test Post",
            "content": "This is a test post",
            "topic": "GENERAL",
            "username": "standardizedquantum",
            "created_at": "2025-07-22T12:00:00Z",
            "comments": []
        }
    ]
}

# Set headers exactly as specified by the client
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

print(f"Headers: {headers}")
print(f"Payload: {json.dumps(payload, indent=2)}")

# Make the request
try:
    # Create a session to preserve headers during redirects
    session = requests.Session()
    
    # Configure the session to preserve the Authorization header during redirects
    session.headers.update(headers)
    
    # Make the request
    response = session.post(
        url,
        data=json.dumps(payload),
        timeout=10
    )
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    print(f"Response headers: {response.headers}")
    print(f"Request URL: {response.request.url}")
    print(f"Request headers: {response.request.headers}")
    print(f"Authorization header present: {'Authorization' in response.request.headers}")
    print(f"Authorization header value: {response.request.headers.get('Authorization', 'Not found')}")
    
except Exception as e:
    print(f"Error: {e}")