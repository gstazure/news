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
        
        # Check if we're using mock mode
        self.use_mock = os.getenv("USE_MOCK_API", "true").lower() == "true"
        print(f"Mock API mode in __init__: {self.use_mock}")
        
        # Get API key
        self.api_key = os.getenv("EXTERNAL_API_KEY")
        print(f"API key from environment: {self.api_key[:10]}...{self.api_key[-10:] if self.api_key else 'None'}")
        print(f"API key length: {len(self.api_key) if self.api_key else 0}")
        
        # If not found, try to read directly from .env file
        if not self.api_key and not self.use_mock:
            try:
                with open('.env', 'r') as f:
                    for line in f:
                        if line.startswith('EXTERNAL_API_KEY='):
                            self.api_key = line.strip().split('=', 1)[1]
                            print(f"API key loaded directly from .env file")
                            break
            except Exception as e:
                print(f"Error reading .env file: {e}")
        
        # Get base URL
        self.base_url = os.getenv("EXTERNAL_API_URL", "https://www.tickertalk.in")
        print(f"Base URL: {self.base_url}")
        print(f"Full API URL will be: {self.base_url}/api/external/bulk-upload-posts-comments")
        
        # Set headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "Bearer mock-key"
        }
        print(f"Authorization header: {self.headers['Authorization']}")
        print(f"TickertalkAPI initialized with API key: {'*' * 8 + self.api_key[-4:] if self.api_key else 'None (Mock mode enabled)'}")
    
    def test_api_connection(self):
        """Test the API connection with different authorization formats"""
        print("Testing API connection with different authorization formats...")
        
        # Test with different authorization formats
        test_headers = [
            {'Content-Type': 'application/json', 'Authorization': self.api_key},  # Raw API key
            {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'},  # Bearer token
            {'Content-Type': 'application/json', 'X-API-Key': self.api_key}
        ]
        
        # Simple test payload
        test_payload = {"test": True}
        
        results = []
        
        for i, headers in enumerate(test_headers):
            try:
                print(f"Test {i+1}: Using headers: {headers}")
                response = requests.post(
                    f"{self.base_url}/api/external/bulk-upload-posts-comments",
                    headers=headers,
                    data=json.dumps(test_payload),
                    timeout=5
                )
                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.text}")
                results.append({
                    "headers": headers,
                    "status": response.status_code,
                    "body": response.text
                })
            except Exception as e:
                print(f"Error: {e}")
                results.append({
                    "headers": headers,
                    "error": str(e)
                })
        
        return results
    
    def publish_post(self, post_data):
        """Publish a post to the external API"""
        print(f"TickertalkAPI.publish_post called with data: {post_data}")
        
        # Check if API key is available
        if not self.api_key and not self.use_mock:
            print("ERROR: API key not configured. Please set EXTERNAL_API_KEY in .env file or enable mock mode.")
            return {
                "success": False,
                "error": "API key not configured. Set EXTERNAL_API_KEY in .env file or enable mock mode."
            }
        
        print(f"Using API key: {self.api_key[:8]}...{self.api_key[-4:]}")
        print(f"API URL: {self.base_url}/api/external/bulk-upload-posts-comments")
        
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
        
        print(f"Making API request to: {self.base_url}/api/external/bulk-upload-posts-comments")
        print(f"Headers: {self.headers}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Check if we should use mock mode
        print(f"Mock API mode enabled: {self.use_mock}")
        if self.use_mock:
            print("Using mock API response for testing (API endpoint may not be available)")
            mock_response = {
                "success": True,
                "total": 1,
                "successful": 1,
                "failed": 0,
                "results": [
                    {
                        "status": "success",
                        "post_id": f"mock-{formatted_post.get('temp_post_id', 'unknown')}",
                        "comments_created": len(formatted_post.get("comments", []))
                    }
                ]
            }
            print(f"Mock API response: {json.dumps(mock_response, indent=2)}")
            return mock_response
        
        # Make the real API request if not in mock mode
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
            print(f"Response headers: {response.headers}")
            print(f"Final request URL: {response.request.url}")
            print(f"Request headers sent: {response.request.headers}")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"API Error: {response.status_code}",
                    "message": response.text
                }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": "Request failed",
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": "Unexpected error",
                "message": str(e)
            }

# Test the API if run directly
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