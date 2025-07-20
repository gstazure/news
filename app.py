from flask import Flask, render_template, request, jsonify, send_file
import csv
import io
from datetime import datetime, timedelta
import json
import os
import requests
from main import process_article, load_topics

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
                seven_days_ago = datetime.now() - timedelta(days=7)
                params = {
                    'api_token': api_token,
                    'search': query,
                    'entity_types': 'equity',
                    'language': 'en',
                    'countries': 'in',
                    'limit': 10,
                    'published_after': seven_days_ago.strftime('%Y-%m-%dT%H:%M:%S')
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
                            'preview': post.get('content', '')[:200] + '...' if len(post.get('content', '')) > 200 else post.get('content', '')
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



if __name__ == '__main__':
    app.run(debug=True)