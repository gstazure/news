import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Make sure to load environment variables
load_dotenv()

class TickertalkAPI:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get API key
        self.api_key = os.getenv("EXTERNAL_API_KEY")
        print(f"API key: {self.api_key[:8]}...{self.api_key[-4:] if self.api_key else 'None'}")
        
        # Get base URL
        self.base_url = os.getenv("EXTERNAL_API_URL", "https://www.tickertalk.in")
        print(f"Base URL: {self.base_url}")
        
        # Set headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        print(f"Headers: {self.headers}")
    
    def publish_post(self, post_data):
        """Publish a post to the external API"""
        # Format the post data
        formatted_post = {
            "temp_post_id": post_data.get("temp_post_id", post_data.get("id", "post_001")),
            "title": post_data.get("title", ""),
            "content": post_data.get("content", ""),
            "topic": post_data.get("topic", "GENERAL"),
            "username": post_data.get("username", "anonymous"),
            "created_at": post_data.get("created_at", datetime.now().isoformat()),
            "comments": []
        }
        
        # Format comments
        for comment in post_data.get("comments", []):
            comment_body = comment.get("body", comment.get("content", ""))
            formatted_comment = {
                "temp_comment_id": comment.get("temp_comment_id", f"comment_{id(comment)}"),
                "body": comment_body,
                "username": comment.get("username", "anonymous"),
                "created_at": comment.get("created_at", datetime.now().isoformat())
            }
            formatted_post["comments"].append(formatted_comment)
        
        # Prepare the payload
        payload = {
            "posts": [formatted_post]
        }
        
        # Make the request
        try:
            # Create a session
            session = requests.Session()
            
            # Set headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            session.headers.update(headers)
            
            # Make the request
            url = f"{self.base_url}/api/external/bulk-upload-posts-comments"
            print(f"URL: {url}")
            print(f"Headers: {session.headers}")
            
            response = session.post(
                url,
                data=json.dumps(payload),
                timeout=10
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "message": response.text
                }
        except Exception as e:
            print(f"Error: {e}")
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }

# Test the API
if __name__ == "__main__":
    api = TickertalkAPI()
    
    # Create a test post
    post = {
        "temp_post_id": "test_001",
        "title": "Test Post",
        "content": "This is a test post",
        "topic": "HINDUNILVR",
        "username": "standardizedquantum",
        "created_at": "2025-07-22T12:00:00Z",
        "comments": []
    }
    
    # Publish the post
    result = api.publish_post(post)
    print(f"Result: {json.dumps(result, indent=2)}")