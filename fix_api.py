import os

# The working code from test_api.py
working_code = '''
    def publish_post(self, post_data):
        """
        Publish a post and its comments to the external API
        
        Args:
            post_data: Dictionary containing post data with comments
            
        Returns:
            dict: API response
        """
        print(f"TickertalkAPI.publish_post called with data: {post_data}")
        
        if not self.api_key and not self.use_mock:
            print("ERROR: API key not configured. Please set EXTERNAL_API_KEY in .env file or enable mock mode.")
            return {
                "success": False,
                "error": "API key not configured. Set EXTERNAL_API_KEY in .env file or enable mock mode."
            }
        
        print(f"Using API key: {self.api_key[:8]}...{self.api_key[-4:]}")
        print(f"API URL: {self.base_url}/api/external/bulk-upload-posts-comments")
            
        # Format the post data according to the API requirements
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
            # Check both body and content fields since some comments might use different field names
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
            # Create a session to preserve headers during redirects
            session = requests.Session()
            
            # Set headers exactly as specified by the client
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Configure the session to preserve the Authorization header during redirects
            session.headers.update(headers)
            
            url = f"{self.base_url}/api/external/bulk-upload-posts-comments"
            
            print(f"Request URL: {url}")
            print(f"Request headers: {session.headers}")
            
            # Make the request exactly as specified by the client
            response = session.post(
                url,
                data=json.dumps(payload),
                timeout=10
            )
            
            print(f"API response status: {response.status_code}")
            print(f"API response body: {response.text}")
            
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
'''

# Read the current external_api.py file
with open('external_api.py', 'r') as f:
    content = f.read()

# Find the start and end of the publish_post method
start_marker = 'def publish_post(self, post_data):'
end_marker = 'def test_api_connection(self):'

# Find the positions
start_pos = content.find(start_marker)
end_pos = content.find(end_marker)

if start_pos == -1 or end_pos == -1:
    print("Could not find the publish_post method in external_api.py")
    exit(1)

# Replace the method
new_content = content[:start_pos] + working_code + content[end_pos:]

# Write the new content back to the file
with open('external_api.py', 'w') as f:
    f.write(new_content)

print("Successfully updated external_api.py with the working code from test_api.py")