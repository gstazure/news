from flask import Flask, render_template, request, jsonify, send_file
import csv
import io
from datetime import datetime, timedelta
import json
import os
import requests
from dotenv import load_dotenv
from main import process_article, load_topics

# Load environment variables from .env file
load_dotenv()
print("Environment variables loaded from .env file")

app = Flask(__name__)

# Ensure output directory exists
if not os.path.exists('outputs'):
    os.makedirs('outputs')

@app.route('/', methods=['GET', 'POST'])
def index():
    news_results = []
    query = ""
    errors = []

    if request.method == 'POST':
        query = request.form.get('query')
        if query:
            api_token = os.getenv('MARKETAUX_API_TOKEN')
            if not api_token:
                errors.append('MARKETAUX_API_TOKEN not found in environment variables.')
            else:
                api_url = 'https://api.marketaux.com/v1/news/all'
                three_days_ago = datetime.now() - timedelta(days=3)
                params = {
                    'api_token': api_token,
                    'search': query,
                    'entity_types': 'equity',
                    'language': 'en',
                    'countries': 'in',
                    'limit': 10,
                    'published_after': three_days_ago.strftime('%Y-%m-%dT%H:%M:%S')
                }
                try:
                    response = requests.get(api_url, params=params)
                    response.raise_for_status()
                    news_data = response.json()
                    news_results = news_data.get('data', [])

                    # Store the news data
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_filename = f'outputs/search_{timestamp}.json'
                    with open(output_filename, 'w', encoding='utf-8') as f:
                        json.dump(news_data, f, indent=2, ensure_ascii=False)

                except requests.exceptions.RequestException as e:
                    errors.append(f"Error fetching news from MarketAux: {e}")
                except Exception as e:
                    errors.append(f"An unexpected error occurred: {e}")
        else:
            errors.append("Please enter a search query.")

    topics = list(load_topics())[:5]
    return render_template('index.html', sample_topics=topics, news_results=news_results, query=query, errors=errors, all_topics=list(load_topics()))

@app.route('/process_selected', methods=['POST'])
def process_selected():
    selected_articles = request.get_json()
    if not selected_articles:
        return jsonify({'error': 'No articles selected'}), 400

    all_posts = {"posts": []}
    errors = []
    success_count = 0

    for article in selected_articles:
        try:
            if not article['url'].strip() or not article['topic'].strip():
                errors.append(f"Invalid data for URL: {article['url']}")
                continue

            available_topics = load_topics()
            if article['topic'] not in available_topics:
                errors.append(f"Invalid topic '{article['topic']}' for URL: {article['url']}")
                continue

            post = process_article(article['url'].strip(), article['topic'].strip())
            if post and post.get("posts"):
                all_posts["posts"].extend(post["posts"])
                success_count += 1
            else:
                errors.append(f"Failed to process article from {article['url']}")
        except Exception as e:
            errors.append(f"Error processing article from {article['url']}: {str(e)}")
            continue

    if success_count == 0:
        return jsonify({
            'error': 'No articles were successfully processed',
            'details': errors
        }), 400

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f'outputs/output_{timestamp}.json'

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(all_posts, f, indent=2, ensure_ascii=False)

    return jsonify({
        'message': f'Successfully processed {success_count} articles',
        'filename': output_filename,
        'data': all_posts,
        'errors': errors if errors else None
    })

@app.route('/download_sample')
def download_sample():
    """Generate and download a sample CSV file"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['topic', 'url'])
    writer.writerow(['NIFTY', 'https://www.moneycontrol.com/news/business/markets/example-1'])
    writer.writerow(['RELIANCE', 'https://www.livemint.com/market/example-2'])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='sample_input.csv'
    )

@app.route('/process', methods=['POST'])
def process_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Please upload a CSV file'}), 400
    
    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        # Validate CSV structure
        if not {'topic', 'url'}.issubset(csv_reader.fieldnames):
            return jsonify({'error': 'CSV must contain "topic" and "url" columns'}), 400

        all_posts = {"posts": []}
        errors = []
        success_count = 0
        
        # Process each row
        for row_num, row in enumerate(csv_reader, start=1):
            try:
                if not row['url'].strip() or not row['topic'].strip():
                    errors.append(f"Row {row_num}: Empty URL or topic")
                    continue
                
                # Validate topic exists
                available_topics = load_topics()
                if row['topic'] not in available_topics:
                    errors.append(f"Row {row_num}: Invalid topic '{row['topic']}'")
                    continue
                
                post = process_article(row['url'].strip(), row['topic'].strip())
                if post and post.get("posts"):
                    all_posts["posts"].extend(post["posts"])
                    success_count += 1
                else:
                    errors.append(f"Row {row_num}: Failed to process article from {row['url']}")
            
            except Exception as e:
                errors.append(f"Row {row_num}: Error - {str(e)}")
                continue  # Continue with next row even if this one fails
        
        # Return successful results even if some rows failed
        if success_count > 0:
            status_code = 200  # Success with some posts
        else:
            return jsonify({
                'error': 'No articles were successfully processed',
                'details': errors
            }), 400
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f'outputs/output_{timestamp}.json'
        
        # Save to file
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(all_posts, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'message': f'Successfully processed {success_count} articles',
            'filename': output_filename,
            'data': all_posts,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to process CSV file',
            'details': str(e)
        }), 500

@app.route('/outputs')
def list_outputs():
    """List all generated output files"""
    files = []
    for file in os.listdir('outputs'):
        if file.endswith('.json'):
            filepath = os.path.join('outputs', file)
            files.append({
                'name': file,
                'size': os.path.getsize(filepath),
                'created': datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
            })
    return jsonify(files)

@app.route('/content')
def content_page():
    """Display generated content in cards"""
    return render_template('content.html')

@app.route('/api/content')
def get_content():
    """API endpoint to get all generated content"""
    content_list = []
    
    if not os.path.exists('outputs'):
        return jsonify(content_list)
    
    for filename in os.listdir('outputs'):
        if filename.endswith('.json') and filename.startswith('output_'):
            filepath = os.path.join('outputs', filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if 'posts' in data and data['posts']:
                    for post_index, post in enumerate(data['posts']):
                        content_item = {
                            'id': post.get('temp_post_id', f"{filename}_{post_index}"),
                            'title': post.get('title', 'No Title'),
                            'content': post.get('content', ''),
                            'topic': post.get('topic', 'GENERAL'),
                            'username': post.get('username', 'Anonymous'),
                            'created_at': post.get('created_at', ''),
                            'comments': post.get('comments', []),
                            'filename': filename,
                            'post_index': post_index,
                            'preview': post.get('content', '')[:200] + '...' if len(post.get('content', '')) > 200 else post.get('content', ''),
                            'published': post.get('published', False),
                            'published_at': post.get('published_at', ''),
                            'external_id': post.get('external_id', '')
                        }
                        content_list.append(content_item)
            except Exception as e:
                print(f"Error reading {filename}: {e}")
                continue
    
    # Sort by created_at descending (newest first)
    content_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(content_list)

def create_backup(filepath):
    """Create a backup of the file before editing"""
    try:
        backup_dir = 'outputs/backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{filename}.backup_{timestamp}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        import shutil
        shutil.copy2(filepath, backup_path)
        return backup_path
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None

def validate_json_structure(data):
    """Validate that the JSON has the expected structure"""
    if not isinstance(data, dict):
        return False
    if 'posts' not in data:
        return False
    if not isinstance(data['posts'], list):
        return False
    
    for post in data['posts']:
        if not isinstance(post, dict):
            return False
        required_fields = ['temp_post_id', 'title', 'content', 'topic', 'username', 'created_at']
        for field in required_fields:
            if field not in post:
                return False
        if 'comments' in post and not isinstance(post['comments'], list):
            return False
    
    return True

@app.route('/api/content/edit', methods=['POST'])
def edit_content():
    """Edit post or comment content"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        content_type = data.get('type')  # 'post' or 'comment'
        
        if not filename or not content_type:
            return jsonify({'error': 'Missing required fields'}), 400
            
        filepath = os.path.join('outputs', filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
            
        # Create backup before editing
        backup_path = create_backup(filepath)
        
        # Read current data
        with open(filepath, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
            
        if content_type == 'post':
            new_title = data.get('title', '').strip()
            new_content = data.get('content', '').strip()
            post_index = data.get('post_index', 0)
            
            if not new_title or not new_content:
                return jsonify({'error': 'Title and content cannot be empty'}), 400
                
            if post_index < len(file_data.get('posts', [])):
                file_data['posts'][post_index]['title'] = new_title
                file_data['posts'][post_index]['content'] = new_content
            else:
                return jsonify({'error': 'Post not found'}), 404
                
        elif content_type == 'comment':
            new_body = data.get('body', '').strip()
            post_index = data.get('post_index', 0)
            comment_index = data.get('comment_index', 0)
            
            if not new_body:
                return jsonify({'error': 'Comment body cannot be empty'}), 400
                
            if (post_index < len(file_data.get('posts', [])) and 
                comment_index < len(file_data['posts'][post_index].get('comments', []))):
                file_data['posts'][post_index]['comments'][comment_index]['body'] = new_body
            else:
                return jsonify({'error': 'Comment not found'}), 404
        else:
            return jsonify({'error': 'Invalid content type'}), 400
            
        # Save updated data
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(file_data, f, indent=2, ensure_ascii=False)
            
        return jsonify({'message': f'{content_type.title()} updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/delete', methods=['POST'])
def delete_content():
    """Delete post or comment content"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        content_type = data.get('type')  # 'post' or 'comment'
        
        if not filename or not content_type:
            return jsonify({'error': 'Missing required fields'}), 400
            
        filepath = os.path.join('outputs', filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
            
        # Create backup before deleting
        backup_path = create_backup(filepath)
        
        # Read current data
        with open(filepath, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
            
        if content_type == 'post':
            post_index = data.get('post_index', 0)
            
            if post_index < len(file_data.get('posts', [])):
                file_data['posts'].pop(post_index)
                
                # If no posts left, delete the file
                if not file_data['posts']:
                    os.remove(filepath)
                    return jsonify({'message': 'Post deleted and file removed'})
            else:
                return jsonify({'error': 'Post not found'}), 404
                
        elif content_type == 'comment':
            post_index = data.get('post_index', 0)
            comment_index = data.get('comment_index', 0)
            
            if (post_index < len(file_data.get('posts', [])) and 
                comment_index < len(file_data['posts'][post_index].get('comments', []))):
                file_data['posts'][post_index]['comments'].pop(comment_index)
            else:
                return jsonify({'error': 'Comment not found'}), 404
        else:
            return jsonify({'error': 'Invalid content type'}), 400
            
        # Save updated data (only if file wasn't deleted)
        if os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2, ensure_ascii=False)
            
        return jsonify({'message': f'{content_type.title()} deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@app.route('/api/test-connection', methods=['GET'])
@app.route('/api/test-connection/<test_type>', methods=['GET'])
@app.route('/api/direct-test', methods=['GET'])
def test_api_connection(test_type=None):
    """Test the API connection with different authorization formats"""
    if request.path == '/api/direct-test':
        return direct_test_connection()
    try:
        print(f"Testing API connection... Type: {test_type}")
        
        # Import the TickertalkAPI class
        from external_api import TickertalkAPI
        
        # Create API instance
        api = TickertalkAPI()
        
        if test_type == "raw":
            # Test with raw API key
            api_key = os.getenv("EXTERNAL_API_KEY")
            headers = {'Content-Type': 'application/json', 'Authorization': api_key}
            print(f"Testing with raw API key: {api_key}")
            response = requests.post(
                f"{api.base_url}/api/external/bulk-upload-posts-comments",
                headers=headers,
                data=json.dumps({"test": True}),
                timeout=5
            )
            return jsonify({
                'success': True,
                'message': 'Raw API key test completed',
                'status': response.status_code,
                'body': response.text
            })
        elif test_type == "bearer":
            # Test with Bearer token
            api_key = os.getenv("EXTERNAL_API_KEY")
            headers = {'Content-Type': 'application/json', 'Authorization': f"Bearer {api_key}"}
            print(f"Testing with Bearer token: Bearer {api_key}")
            response = requests.post(
                f"{api.base_url}/api/external/bulk-upload-posts-comments",
                headers=headers,
                data=json.dumps({"test": True}),
                timeout=5
            )
            return jsonify({
                'success': True,
                'message': 'Bearer token test completed',
                'status': response.status_code,
                'body': response.text
            })
        else:
            # Test connection with all formats
            results = api.test_api_connection()
            
            return jsonify({
                'success': True,
                'message': 'API connection test completed',
                'results': results
            })
        
    except Exception as e:
        print(f"Error testing API connection: {e}")
        return jsonify({'error': f'Failed to test API connection: {str(e)}'}), 500

@app.route('/api/publish/<post_id>', methods=['POST'])
def publish_post(post_id):
    """Publish a post to the external API"""
    try:
        print(f"Publishing post with ID: {post_id}")
        data = request.get_json()
        print(f"Request data: {data}")
        
        # Check if API key is available
        api_key = os.getenv("EXTERNAL_API_KEY")
        if not api_key:
            print("ERROR: EXTERNAL_API_KEY not found in environment variables")
            print(f"Available environment variables: {[k for k in os.environ.keys() if not k.startswith('_')]}")
            return jsonify({
                'success': False,
                'error': 'API key not configured',
                'message': 'EXTERNAL_API_KEY not found in environment variables'
            }), 400
        else:
            print(f"API key found: {api_key[:5]}...{api_key[-5:]}")
            print(f"API key length: {len(api_key)}")
            print(f"API key type: {type(api_key)}")
            print(f"API key contains whitespace: {any(c.isspace() for c in api_key)}")
            
            # Direct test from app.py
            try:
                import requests
                import json
                
                # Create a session
                test_session = requests.Session()
                
                # Set headers
                test_headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                test_session.headers.update(test_headers)
                
                # Make a test request
                test_url = f"{os.getenv('EXTERNAL_API_URL', 'https://www.tickertalk.in')}/api/external/bulk-upload-posts-comments"
                test_payload = {
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
                
                print(f"App.py direct test - URL: {test_url}")
                print(f"App.py direct test - Headers: {test_headers}")
                
                test_response = test_session.post(
                    test_url,
                    data=json.dumps(test_payload),
                    timeout=10
                )
                
                print(f"App.py direct test - Response status: {test_response.status_code}")
                print(f"App.py direct test - Response body: {test_response.text}")
                
            except Exception as e:
                print(f"App.py direct test failed: {e}")
        
        filename = data.get('filename')
        post_index = data.get('post_index')
        
        if not filename or post_index is None:
            print(f"Missing parameters: filename={filename}, post_index={post_index}")
            return jsonify({'error': 'Missing required parameters'}), 400
            
        filepath = os.path.join('outputs', filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
            
        # Read the post data
        with open(filepath, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
            
        if post_index >= len(file_data.get('posts', [])):
            return jsonify({'error': 'Post index out of range'}), 400
            
        post_data = file_data['posts'][post_index]
        
        # Import the TickertalkAPI class
        from external_api import TickertalkAPI
        
        # Publish the post
        api = TickertalkAPI()
        result = api.publish_post(post_data)
        
        # Update the post with published status if successful
        if result.get('success'):
            post_data['published'] = True
            post_data['published_at'] = datetime.now().isoformat()
            post_data['external_id'] = result.get('results', [{}])[0].get('post_id')
            
            # Save the updated data
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2, ensure_ascii=False)
            
            # Check if we're using mock mode
            use_mock = os.getenv("USE_MOCK_API", "true").lower() == "true"
            print(f"Mock API mode in app.py: {use_mock}")
            if use_mock:
                result['message'] = "Post published successfully (using mock API)"
                print("Using mock API mode - post marked as published")
            else:
                result['message'] = "Post published successfully"
            
        return jsonify(result)
        
    except Exception as e:
        print(f"Error publishing post: {e}")
        return jsonify({'error': f'Failed to publish post: {str(e)}'}), 500

def direct_test_connection():
    """Test the API connection using urllib directly"""
    try:
        import urllib.request
        import urllib.error
        import json
        
        # Get API key and URL
        api_key = os.getenv("EXTERNAL_API_KEY")
        base_url = os.getenv("EXTERNAL_API_URL", "https://tickertalk.in")
        
        # Try both with and without trailing slash
        if base_url.endswith('/'):
            base_url_no_slash = base_url[:-1]
            base_url_with_slash = base_url
        else:
            base_url_no_slash = base_url
            base_url_with_slash = base_url + '/'
            
        # Try with trailing slash first
        url = f"{base_url_with_slash}api/external/bulk-upload-posts-comments"
        print(f"Direct test - Using URL with trailing slash: {url}")
        print(f"Direct test - Base URL: {base_url}")
        print(f"Direct test - Full URL: {url}")
        
        # Create test payload
        payload = {
            "posts": [
                {
                    "temp_post_id": "test_001",
                    "title": "Test Post",
                    "content": "This is a test post",
                    "topic": "GENERAL",
                    "username": "test_user",
                    "created_at": datetime.now().isoformat(),
                    "comments": []
                }
            ]
        }
        
        # Encode payload
        data = json.dumps(payload).encode('utf-8')
        
        # Create request with explicit headers
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {api_key}')
        
        # Create an opener that handles redirects
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        urllib.request.install_opener(opener)
        
        print(f"Direct test - Request URL: {url}")
        print(f"Direct test - API key: {api_key[:10]}...{api_key[-10:]}")
        print(f"Direct test - Request headers: {req.headers}")
        print(f"Direct test - Request payload: {json.dumps(payload, indent=2)}")
        
        try:
            # Make the request
            response = urllib.request.urlopen(req, timeout=10)
            response_data = response.read().decode('utf-8')
            response_code = response.getcode()
            
            print(f"Direct test - API response status: {response_code}")
            print(f"Direct test - API response body: {response_data}")
            
            # Try to parse JSON response, but handle errors gracefully
            try:
                parsed_body = json.loads(response_data) if response_data else None
            except json.JSONDecodeError:
                parsed_body = {"raw_text": response_data}
                
            return jsonify({
                'success': True,
                'message': 'Direct API test completed',
                'status': response_code,
                'body': parsed_body
            })
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"Direct test - HTTP Error: {e.code} - {e.reason}")
            print(f"Direct test - Response body: {error_body}")
            
            # Try to parse JSON response, but handle errors gracefully
            try:
                parsed_body = json.loads(error_body) if error_body else None
            except json.JSONDecodeError:
                parsed_body = {"raw_text": error_body}
                
            return jsonify({
                'success': False,
                'message': f'Direct API test failed with HTTP error {e.code}',
                'status': e.code,
                'error': e.reason,
                'body': parsed_body
            })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in direct test: {e}")
        print(f"Error details: {error_details}")
        return jsonify({
            'error': f'Failed to perform direct test: {str(e)}',
            'details': error_details
        }), 500
if __name__ == '__main__':
    app.run(debug=True)@app.r
oute('/api/ping-test', methods=['GET'])
def ping_test():
    """Simple test to check if we can connect to the API server"""
    try:
        import urllib.request
        import urllib.error
        
        # Get base URL
        base_url = os.getenv("EXTERNAL_API_URL", "https://tickertalk.in")
        
        # Make sure the base URL doesn't have a trailing slash
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        
        print(f"Ping test - Base URL: {base_url}")
        
        try:
            # Try to connect to the base URL
            response = urllib.request.urlopen(base_url, timeout=10)
            response_data = response.read().decode('utf-8')
            response_code = response.getcode()
            
            print(f"Ping test - Response status: {response_code}")
            print(f"Ping test - Response length: {len(response_data)} characters")
            
            return jsonify({
                'success': True,
                'message': f'Successfully connected to {base_url}',
                'status': response_code
            })
        except urllib.error.HTTPError as e:
            print(f"Ping test - HTTP Error: {e.code} - {e.reason}")
            
            return jsonify({
                'success': False,
                'message': f'HTTP error when connecting to {base_url}',
                'status': e.code,
                'error': e.reason
            })
        except urllib.error.URLError as e:
            print(f"Ping test - URL Error: {e.reason}")
            
            return jsonify({
                'success': False,
                'message': f'Failed to connect to {base_url}',
                'error': str(e.reason)
            })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in ping test: {e}")
        print(f"Error details: {error_details}")
        
        return jsonify({
            'error': f'Failed to perform ping test: {str(e)}',
            'details': error_details
        }), 500@app.ro
ute('/api/requests-test', methods=['GET'])
def requests_test():
    """Test the API connection using the requests library with proper redirect handling"""
    try:
        import requests
        import json
        
        # Get API key and URL
        api_key = os.getenv("EXTERNAL_API_KEY")
        base_url = os.getenv("EXTERNAL_API_URL", "https://tickertalk.in")
        
        # Make sure the base URL doesn't have a trailing slash
        if base_url.endswith('/'):
            base_url = base_url[:-1]
            
        url = f"{base_url}/api/external/bulk-upload-posts-comments"
        
        # Create test payload
        payload = {
            "posts": [
                {
                    "temp_post_id": "test_001",
                    "title": "Test Post",
                    "content": "This is a test post",
                    "topic": "GENERAL",
                    "username": "test_user",
                    "created_at": datetime.now().isoformat(),
                    "comments": []
                }
            ]
        }
        
        # Set headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        print(f"Requests test - URL: {url}")
        print(f"Requests test - Headers: {headers}")
        print(f"Requests test - Payload: {json.dumps(payload, indent=2)}")
        
        # Make the request with allow_redirects=True
        response = requests.post(
            url,
            headers=headers,
            json=payload,  # Use json parameter to automatically handle JSON encoding
            allow_redirects=True,  # Explicitly allow redirects
            timeout=10
        )
        
        print(f"Requests test - Response status: {response.status_code}")
        print(f"Requests test - Response body: {response.text}")
        print(f"Requests test - Response headers: {response.headers}")
        print(f"Requests test - Request URL: {response.request.url}")  # Final URL after redirects
        print(f"Requests test - Request headers: {response.request.headers}")
        
        # Try to parse JSON response, but handle errors gracefully
        try:
            parsed_body = response.json() if response.text else None
        except json.JSONDecodeError:
            parsed_body = {"raw_text": response.text}
            
        return jsonify({
            'success': response.status_code == 200,
            'message': 'Requests API test completed',
            'status': response.status_code,
            'body': parsed_body,
            'final_url': response.request.url,
            'request_headers': dict(response.request.headers)
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in requests test: {e}")
        print(f"Error details: {error_details}")
        
        return jsonify({
            'error': f'Failed to perform requests test: {str(e)}',
            'details': error_details
        }), 500

@app.route('/api-test')
def api_test_page():
    """Display a simple form to test the API directly"""
    api_key = os.getenv("EXTERNAL_API_KEY")
    api_url = f"{os.getenv('EXTERNAL_API_URL', 'https://www.tickertalk.in')}/api/external/bulk-upload-posts-comments"
    return render_template('api_test.html', api_key=api_key, api_url=api_url)

@app.route('/api/direct-publish-test', methods=['GET'])
def direct_publish_test():
    """Test publishing using the exact same code as the test script"""
    try:
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
        
        return jsonify({
            'success': response.status_code == 200,
            'status': response.status_code,
            'body': response.json() if response.text else None,
            'headers': dict(response.request.headers),
            'url': response.request.url
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        return jsonify({
            'error': f'Failed to perform direct publish test: {str(e)}',
            'details': error_details
        }), 500