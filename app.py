from flask import Flask, render_template, request, jsonify, send_file
import csv
import io
from datetime import datetime, timedelta
import json
import os
import requests
from dotenv import load_dotenv
from main import process_article, load_topics
from database import db
import re
import glob

# Load environment variables from .env file
load_dotenv()
print("Environment variables loaded from .env file")

app = Flask(__name__)

# Cache busting functionality
import time

def get_cache_bust_id():
    """Generate a cache-busting ID based on current timestamp"""
    return str(int(time.time()))

# Add cache busting to all template renders
@app.context_processor
def inject_cache_bust():
    return {'cache_bust_id': get_cache_bust_id()}

# Add no-cache headers to all responses
@app.after_request
def add_no_cache_headers(response):
    """Add no-cache headers to prevent browser caching"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def strip_html_tags(text):
    """Remove HTML tags from text for preview generation"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

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
    
    # If this is an AJAX request or API call, return JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        return jsonify({
            'news_results': news_results,
            'query': query,
            'errors': errors
        })
    
    return render_template('index.html', sample_topics=topics, news_results=news_results, query=query, errors=errors, all_topics=list(load_topics()))

@app.route('/process_selected', methods=['POST'])
def process_selected():
    """
    Accepts a JSON array of articles: [{ "topic": "...", "url": "..." }, ...]
    Also supports a single object payload {"topic": "...", "url": "..."} by normalizing to a list.
    Returns consolidated posts JSON with partial success semantics.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({'error': 'Invalid or empty JSON payload'}), 400

    # Normalize payload to list
    if isinstance(payload, dict):
        selected_articles = [payload]
    elif isinstance(payload, list):
        selected_articles = payload
    else:
        return jsonify({'error': 'Payload must be a JSON object or array'}), 400

    all_posts = {"posts": []}
    errors = []
    success_count = 0

    for idx, article in enumerate(selected_articles, start=1):
        try:
            # Validate article structure
            if not isinstance(article, dict):
                errors.append(f"Item {idx}: Expected object with 'url' and 'topic', got {type(article).__name__}")
                continue

            url = str(article.get('url', '')).strip()
            topic = str(article.get('topic', '')).strip()

            if not url or not topic:
                errors.append(f"Item {idx}: Empty URL or topic")
                continue

            # Validate topic exists
            available_topics = load_topics()
            if topic not in available_topics:
                errors.append(f"Item {idx}: Invalid topic '{topic}' for URL: {url}")
                continue

            post = process_article(url, topic)
            if post and post.get("posts"):
                all_posts["posts"].extend(post["posts"])
                success_count += 1
            elif post and post.get("error"):
                errors.append(f"Item {idx}: {post['message']} (URL: {url})")
            else:
                errors.append(f"Item {idx}: Failed to process article from {url} (unknown error)")
        except Exception as e:
            # Avoid indexing into non-dict again
            safe_url = url if 'url' in locals() else '<unknown>'
            errors.append(f"Item {idx}: Error processing article from {safe_url}: {str(e)}")
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
                elif post and post.get("error"):
                    errors.append(f"Row {row_num}: {post['message']} (URL: {row['url']})")
                else:
                    errors.append(f"Row {row_num}: Failed to process article from {row['url']} (unknown error)")
            
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

@app.route('/scraped-news')
def scraped_news_page():
    """Display scraped news articles in cards"""
    return render_template('scraped-news.html')

@app.route('/unified')
def unified_dashboard():
    """Display unified dashboard with all functionality"""
    return render_template('unified.html')

@app.route('/api/topics')
def get_topics():
    """API endpoint to get all available topics"""
    try:
        topics = list(load_topics())
        return jsonify({
            'success': True,
            'topics': topics
        })
    except Exception as e:
        print(f"Error loading topics: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'topics': ['NIFTY', 'BANKNIFTY', 'STOCKS', 'IPO', 'GENERAL']  # Fallback
        })

@app.route('/api/content')
def get_content():
    """API endpoint to get all generated content"""
    content_list = []
    
    # First, load from JSON files (existing method)
    if os.path.exists('outputs'):
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
                                'preview': strip_html_tags(post.get('content', ''))[:200] + '...' if len(strip_html_tags(post.get('content', ''))) > 200 else strip_html_tags(post.get('content', '')),
                                'published': post.get('published', False),
                                'published_at': post.get('published_at', ''),
                                'external_id': post.get('external_id', ''),
                                'source': 'file'
                            }
                            content_list.append(content_item)
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
                    continue
    
    # FALLBACK: Also load from database (for posts generated via unified dashboard)
    try:
        db_posts = db.get_all_posts()
        for db_post in db_posts:
            try:
                output_data = json.loads(db_post['output'])
                if 'posts' in output_data and output_data['posts']:
                    for post_index, post in enumerate(output_data['posts']):
                        # Check if this post is already in content_list (avoid duplicates)
                        post_id = post.get('temp_post_id', f"db_{db_post['url']}_{post_index}")
                        if not any(item['id'] == post_id for item in content_list):
                            content_item = {
                                'id': post_id,
                                'title': post.get('title', 'No Title'),
                                'content': post.get('content', ''),
                                'topic': post.get('topic', 'GENERAL'),
                                'username': post.get('username', 'Anonymous'),
                                'created_at': post.get('created_at', ''),
                                'comments': post.get('comments', []),
                                'filename': f"database_{db_post['created_at']}",
                                'post_index': post_index,
                                'preview': strip_html_tags(post.get('content', ''))[:200] + '...' if len(strip_html_tags(post.get('content', ''))) > 200 else strip_html_tags(post.get('content', '')),
                                'published': post.get('published', False),
                                'published_at': post.get('published_at', ''),
                                'external_id': post.get('external_id', ''),
                                'source': 'database'
                            }
                            content_list.append(content_item)
            except Exception as e:
                print(f"Error processing database post: {e}")
                continue
    except Exception as e:
        print(f"Error loading from database: {e}")
    
    # Sort by created_at descending (newest first)
    content_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(content_list)

@app.route('/api/scrape-article', methods=['POST'])
def scrape_article():
    """Scrape a single article and store in database without generating post"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'success': False, 'error': 'URL is required'}), 400
        
        # Check if already scraped
        existing_article = db.get_article(url)
        if existing_article:
            return jsonify({
                'success': True,
                'message': 'Article already scraped',
                'article': existing_article
            })
        
        # Import the scraper function
        from news_scraper import extract_article
        
        # Scrape the article
        article = extract_article(url)
        if not article:
            return jsonify({'success': False, 'error': 'Failed to extract article content'}), 400
        
        # Save to database
        db.save_article(url, article['title'], article['text'])
        
        return jsonify({
            'success': True,
            'message': 'Article scraped successfully',
            'article': {
                'url': url,
                'title': article['title'],
                'text': article['text'],
                'word_count': len(article['text'].split()) if article['text'] else 0
            }
        })
        
    except Exception as e:
        print(f"Error scraping article: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scraped-articles')
def get_scraped_articles():
    """API endpoint to get all scraped articles from database"""
    try:
        articles = db.get_all_articles()
        
        # Format articles for frontend display
        article_list = []
        for article in articles:
            # Create preview from text
            text = article.get('text', '')
            preview = text[:300] + '...' if len(text) > 300 else text
            
            article_item = {
                'id': f"article_{hash(article['url'])}",
                'url': article['url'],
                'title': article.get('title', 'No Title'),
                'text': text,
                'preview': preview,
                'extracted_at': article.get('extracted_at', ''),
                'source_domain': extract_domain(article['url']),
                'word_count': len(text.split()) if text else 0
            }
            article_list.append(article_item)
        
        # Sort by extracted_at descending (newest first)
        article_list.sort(key=lambda x: x.get('extracted_at', ''), reverse=True)
        return jsonify(article_list)
        
    except Exception as e:
        print(f"Error fetching scraped articles: {e}")
        return jsonify([])

@app.route('/api/search-news', methods=['POST'])
def search_news_api():
    """API endpoint for news search"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'error': 'Search query is required'}), 400
        
        api_token = os.getenv('MARKETAUX_API_TOKEN')
        if not api_token:
            return jsonify({'success': False, 'error': 'API token not configured'}), 500
        
        api_url = 'https://api.marketaux.com/v1/news/all'
        three_days_ago = datetime.now() - timedelta(days=3)
        params = {
            'api_token': api_token,
            'search': query,
            'entity_types': 'equity',
            'language': 'en',
            'countries': 'in',
            'limit': 15,
            'published_after': three_days_ago.strftime('%Y-%m-%dT%H:%M:%S')
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        news_data = response.json()
        news_results = news_data.get('data', [])
        
        # Format results for frontend
        formatted_results = []
        for article in news_results:
            formatted_results.append({
                'url': article.get('url', ''),
                'title': article.get('title', ''),
                'description': article.get('description', ''),
                'source': article.get('source', ''),
                'published_on': article.get('published_at', ''),
                'image_url': article.get('image_url', ''),
                'snippet': article.get('snippet', '')
            })
        
        return jsonify({
            'success': True,
            'results': formatted_results,
            'query': query,
            'count': len(formatted_results)
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': f'News API error: {str(e)}'}), 500
    except Exception as e:
        print(f"Search API error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-post', methods=['POST'])
def generate_post_from_scraped():
    """Generate a forum post from a scraped article"""
    try:
        data = request.get_json()
        url = data.get('url')
        topic = data.get('topic')
        
        if not url or not topic:
            return jsonify({'success': False, 'error': 'URL and topic are required'}), 400
        
        # Check if article exists in database
        article = db.get_article(url)
        if not article:
            return jsonify({'success': False, 'error': 'Article not found in database. Please scrape it first.'}), 404
        
        # Generate the post using existing process_article function
        result = process_article(url, topic)
        
        if result and result.get('posts'):
            # IMPORTANT: Also save to JSON file so it appears in /api/content
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'outputs/output_unified_{timestamp}.json'
            
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"DEBUG: Saved unified post to {output_filename}")
            except Exception as e:
                print(f"WARNING: Failed to save to JSON file: {e}")
            
            return jsonify({
                'success': True,
                'message': 'Post generated successfully',
                'post': result['posts'][0] if result['posts'] else None
            })
        elif result and result.get('error'):
            return jsonify({'success': False, 'error': result['message']}), 400
        else:
            return jsonify({'success': False, 'error': 'Failed to generate post'}), 500
            
    except Exception as e:
        print(f"Error generating post: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def extract_domain(url):
    """Extract domain from URL for display"""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except:
        return 'Unknown'

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
# Move test/diagnostic routes above the __main__ guard and fix decorators

@app.route('/api/ping-test', methods=['GET'])
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
        }), 500


@app.route('/api/requests-test', methods=['GET'])
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


# Workflow Management API Endpoints

@app.route('/workflow')
def workflow():
    """Main workflow management page"""
    return render_template('workflow.html')

def _get_action_buttons(item):
    buttons = []
    # Preview button is always available
    buttons.append(
        f'<button class="action-btn btn-preview" data-action="preview" data-item-id="{item["id"]}" title="Preview">'
        '<i class="fas fa-eye"></i>'
        '</button>'
    )

    # Add other buttons based on type and status
    if item['type'] == 'search_result' and item['status'] == 'pending':
        buttons.append(
            f'<button class="action-btn btn-parse" data-action="parse" data-item-id="{item["id"]}" title="Parse Article">'
            '<i class="fas fa-download"></i>'
            '</button>'
        )
    elif item['type'] == 'parsed_news' and item['status'] == 'pending':
        buttons.append(
            f'<button class="action-btn btn-generate" data-action="generate" data-item-id="{item["id"]}" title="Generate Post">'
            '<i class="fas fa-magic"></i>'
            '</button>'
        )
    elif item['type'] == 'generated_post' and item['status'] == 'pending':
        buttons.append(
            f'<button class="action-btn btn-publish" data-action="publish" data-item-id="{item["id"]}" title="Publish Post">'
            '<i class="fas fa-share"></i>'
            '</button>'
        )
    
    return ' '.join(buttons)

def _process_item_for_response(item):
    # Add the server-generated action buttons HTML to the item dictionary
    item['actions_html'] = _get_action_buttons(item)
    if 'children' in item:
        item['children'] = [_process_item_for_response(child) for child in item['children']]
    return item

@app.route('/api/workflow-items')
def get_workflow_items():
    """Get all workflow items in hierarchical structure with server-side generated actions"""
    try:
        hierarchy = db.get_workflow_hierarchy()
        # Process each item in the hierarchy to add the actions_html
        processed_hierarchy = [_process_item_for_response(item) for item in hierarchy]
        return jsonify(processed_hierarchy)
    except Exception as e:
        print(f"Error fetching workflow items: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow-items', methods=['POST'])
def create_workflow_item():
    """Create a new workflow item from search results"""
    try:
        data = request.get_json()
        search_results = data.get('search_results', [])
        
        created_items = []
        for result in search_results:
            item_id = db.create_workflow_item(
                item_type='search_result',
                title=result.get('title', 'Untitled'),
                url=result.get('url'),
                metadata={
                    'source': result.get('source', ''),
                    'published_date': result.get('published_date', ''),
                    'description': result.get('description', '')
                }
            )
            created_items.append(item_id)
        
        return jsonify({
            'success': True,
            'created_items': created_items,
            'message': f'Created {len(created_items)} workflow items'
        })
    except Exception as e:
        print(f"Error creating workflow items: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow-items/<int:item_id>/parse', methods=['POST'])
def parse_workflow_item(item_id):
    """Parse a search result URL to extract article content"""
    try:
        from news_scraper import extract_article
        
        item = db.get_workflow_item(item_id)
        if not item or item['type'] != 'search_result':
            return jsonify({'error': 'Invalid item or not a search result'}), 400
        
        # Update status to processing
        db.update_workflow_item(item_id, status='processing')
        
        # Extract article using existing working function
        result = extract_article(item['url'])
        if result and result.get('title') and result.get('text'):
            # Create parsed news child item
            parsed_id = db.create_workflow_item(
                item_type='parsed_news',
                title=result['title'],
                url=item['url'],
                content=result['text'],  # Use 'text' field from extract_article
                parent_id=item_id,
                metadata={
                    'extraction_method': 'news_scraper',
                    'original_search_title': item['title']
                }
            )
            
            # Update parent status
            db.update_workflow_item(item_id, status='completed')
            
            # Also save to existing articles table for compatibility
            db.save_article(item['url'], result['title'], result['text'])
            
            return jsonify({
                'success': True,
                'parsed_item_id': parsed_id,
                'title': result['title'],
                'word_count': len(result['text'].split()),
                'message': 'Article parsed successfully'
            })
        else:
            db.update_workflow_item(item_id, status='failed')
            return jsonify({'error': 'Failed to parse article - no content extracted'}), 500
            
    except Exception as e:
        print(f"Error parsing workflow item: {e}")
        db.update_workflow_item(item_id, status='failed')
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow-items/<int:item_id>/generate', methods=['POST'])
def generate_post_from_workflow(item_id):
    """Generate post from parsed news item"""
    print(f"=== POST GENERATION START ===")
    print(f"Item ID: {item_id}")
    
    try:
        data = request.get_json()
        topic = data.get('topic', 'GENERAL')
        print(f"Topic: {topic}")
        
        item = db.get_workflow_item(item_id)
        if not item or item['type'] != 'parsed_news':
            print(f"ERROR: Invalid item - Type: {item['type'] if item else 'None'}")
            return jsonify({'error': 'Invalid item or not parsed news'}), 400
        
        print(f"Item details - Title: {item['title'][:50]}..., URL: {item['url']}")
        print(f"Item content length: {len(item.get('content', ''))} chars")
        
        # Update status to processing
        db.update_workflow_item(item_id, status='processing')
        print(f"Updated item status to 'processing'")
        
        # Generate post using existing process_article function
        print(f"Calling process_article with URL: {item['url']}, Topic: {topic}")
        result = process_article(item['url'], forced_topic=topic)
        print(f"process_article returned: {type(result)}")
        
        if result:
            print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            if isinstance(result, dict) and 'error' in result:
                print(f"ERROR in result: {result['error']} - {result.get('message', '')}")
                db.update_workflow_item(item_id, status='failed')
                return jsonify({'error': result['message']}), 500
        
        if result and result.get('posts'):
            post_data = result['posts'][0]
            print(f"Generated post title: {post_data.get('title', 'No title')}")
            print(f"Generated post content length: {len(post_data.get('content', ''))}")
            
            # Create generated post child item
            post_id = db.create_workflow_item(
                item_type='generated_post',
                title=post_data.get('title', 'Generated Post'),
                url=item['url'],
                content=post_data.get('content', ''),
                parent_id=item_id,
                metadata={
                    'topic': topic,
                    'username': post_data.get('username', ''),
                    'generation_method': 'openrouter_api',
                    'temp_post_id': post_data.get('temp_post_id', '')
                }
            )
            
            # Update parent to completed (post has been generated)
            # Generated post starts as pending (until published)
            db.update_workflow_item(item_id, status='completed')  # Update parent (parsed_news) - post generated
            # post_id starts as pending by default - ready to be published
            print(f"Created generated post with ID: {post_id}")
            
            # Save to JSON file for compatibility
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f'outputs/output_workflow_{timestamp}.json'
            try:
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"Saved output to: {output_filename}")
            except Exception as e:
                print(f"WARNING: Failed to save to JSON file: {e}")
            
            print(f"=== POST GENERATION SUCCESS ===")
            return jsonify({
                'success': True,
                'post_item_id': post_id,
                'post': post_data,
                'message': 'Post generated successfully'
            })
        else:
            print(f"ERROR: No posts in result or result is None")
            print(f"Result value: {result}")
            db.update_workflow_item(item_id, status='failed')
            return jsonify({'error': 'Failed to generate post - no content returned'}), 500
            
    except Exception as e:
        print(f"EXCEPTION in generate_post_from_workflow: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        try:
            db.update_workflow_item(item_id, status='failed')
        except Exception as db_error:
            print(f"Additional error updating item status: {db_error}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow-items/<int:item_id>/publish', methods=['POST'])
def publish_workflow_post(item_id):
    """Publish generated post to external API"""
    try:
        item = db.get_workflow_item(item_id)
        if not item or item['type'] != 'generated_post':
            return jsonify({'error': 'Invalid item or not a generated post'}), 400
        
        print(f"Publishing workflow post with ID: {item_id}")
        print(f"Post title: {item['title']}")
        print(f"Post metadata: {item.get('metadata', {})}")
        
        # Update status to processing
        db.update_workflow_item(item_id, status='processing')
        
        # Get the temp_post_id from metadata
        metadata = item.get('metadata', {})
        temp_post_id = metadata.get('temp_post_id')
        
        if not temp_post_id:
            print(f"No temp_post_id found in metadata, generating one")
            import time
            import random
            timestamp = str(int(time.time()))[-6:]
            random_num = random.randint(100, 999)
            temp_post_id = f"workflow_{timestamp}_{random_num}"
        
        # Try to load comments/replies from existing JSON files like content page does
        comments = []
        try:
            output_files = glob.glob(os.path.join('outputs', 'output_*.json'))
            for filepath in output_files:
                with open(filepath, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    posts = file_data.get('posts', [])
                    for post in posts:
                        if post.get('temp_post_id') == temp_post_id:
                            comments = post.get('comments', [])
                            print(f"Found {len(comments)} comments for temp_post_id: {temp_post_id}")
                            break
                    if comments:
                        break
        except Exception as e:
            print(f"Error loading comments: {e}")
            comments = []
        
        # Create post data in the same format as the working publish endpoint
        post_data = {
            'temp_post_id': temp_post_id,
            'title': item['title'],
            'content': item['content'],
            'topic': metadata.get('topic', 'GENERAL'),
            'username': metadata.get('username', 'standardizedquantum'),
            'created_at': item['created_at'],
            'comments': comments  # Include any existing comments/replies
        }
        
        print(f"Publishing post data: {post_data}")
        
        # Import and use the same TickertalkAPI class as the working publish endpoint
        from external_api import TickertalkAPI
        
        api = TickertalkAPI()
        result = api.publish_post(post_data)
        
        print(f"=== PUBLISH RESULT FROM TICKERTALK ===")
        print(f"Full result: {result}")
        print(f"Success: {result.get('success')}")
        print(f"Error: {result.get('error')}")
        print(f"Message: {result.get('message')}")
        if 'results' in result:
            print(f"Results: {result['results']}")
        print(f"=====================================")
        
        # Check if the post was actually successfully published
        # TickerTalk returns success=true even when posts fail
        # We need to check the individual post result
        post_published_successfully = False
        if result.get('success') and result.get('results'):
            first_result = result['results'][0]
            if first_result.get('status') == 'success' or (result.get('successful', 0) > 0):
                post_published_successfully = True
        
        if post_published_successfully:
            # Update workflow item with published status - change from pending to completed
            db.update_workflow_item(item_id, status='completed', metadata={
                **metadata,
                'published': True,
                'published_at': datetime.now().isoformat(),
                'external_id': result.get('results', [{}])[0].get('post_id') if result.get('results') else None,
                'temp_post_id': temp_post_id,
                'publish_response': result  # Store the full response for debugging
            })
            
            # Check if we're using mock mode
            use_mock = os.getenv("USE_MOCK_API", "true").lower() == "true"
            if use_mock:
                result['message'] = "Post published successfully (using mock API)"
                print("Using mock API mode - post marked as published")
            else:
                # Show detailed success message with external validation
                if result.get('results') and result['results'][0].get('post_id'):
                    result['message'] = f"Post published successfully to TickerTalk (ID: {result['results'][0]['post_id']})"
                else:
                    result['message'] = "Post published successfully (no external ID returned)"
            
            return jsonify(result)
        else:
            # Publishing failed - extract the actual error message
            error_message = "Failed to publish post"
            if result.get('results') and result['results'][0].get('message'):
                error_message = result['results'][0]['message']
            elif result.get('message'):
                error_message = result['message']
            elif result.get('error'):
                error_message = result['error']
            
            db.update_workflow_item(item_id, status='failed')
            return jsonify({
                'success': False,
                'error': error_message,
                'message': f"TickerTalk rejected the post: {error_message}"
            }), 400
        
    except Exception as e:
        print(f"Error publishing workflow post: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        db.update_workflow_item(item_id, status='failed')
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow-items/<int:item_id>/preview')
def preview_workflow_item(item_id):
    """Get preview data for workflow item"""
    try:
        item = db.get_workflow_item(item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        
        preview_data = {
            'id': item['id'],
            'type': item['type'],
            'title': item['title'],
            'url': item.get('url'),
            'content': item.get('content', ''),
            'word_count': item.get('word_count', 0),
            'status': item['status'],
            'created_at': item['created_at'],
            'metadata': item.get('metadata', {})
        }
        
        return jsonify(preview_data)
        
    except Exception as e:
        print(f"Error getting preview: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/workflow-items/<int:item_id>', methods=['PATCH'])
def update_workflow_item_content(item_id):
    """Update workflow item content and title"""
    try:
        data = request.get_json()
        
        item = db.get_workflow_item(item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404
        
        # Only allow editing parsed_news and generated_post
        if item['type'] not in ['parsed_news', 'generated_post']:
            return jsonify({'error': 'Item type not editable'}), 400
        
        update_fields = {}
        
        # Update content if provided
        if 'content' in data:
            update_fields['content'] = data['content']
            # Recalculate word count
            import re
            text_content = re.sub(r'<[^>]*>', '', data['content'])  # Strip HTML
            word_count = len(text_content.split()) if text_content.strip() else 0
            update_fields['word_count'] = word_count
        
        # Update title if provided (for generated posts)
        if 'title' in data and item['type'] == 'generated_post':
            # Ensure title is plain text and within limits
            title = data['title'].strip()
            title = re.sub(r'<[^>]*>', '', title)  # Strip HTML
            title = title.replace('<', '').replace('>', '')  # Remove angle brackets
            if len(title) > 150:
                title = title[:150].rstrip()
                last_space = title.rfind(' ')
                if last_space > 20:  # Don't cut too early
                    title = title[:last_space]
            update_fields['title'] = title
        
        if not update_fields:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        print(f"Updating workflow item {item_id} with fields: {list(update_fields.keys())}")
        
        # Update the item
        db.update_workflow_item(item_id, **update_fields)
        
        return jsonify({'message': 'Item updated successfully'})
        
    except Exception as e:
        print(f"Error updating workflow item: {e}")
        return jsonify({'error': str(e)}), 500

# Ensure the app entrypoint is the last thing in the file
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)