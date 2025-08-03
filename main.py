import json
import os
import random
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from database import db  # Import database module

from news_scraper import extract_article
from postgen import generate_post
from replies import generate_reply

load_dotenv()

def generate_temp_id(prefix, index):
    """Generate a unique temporary ID using timestamp and random number"""
    import time
    timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
    random_num = random.randint(100, 999)
    return f"{prefix}_{timestamp}_{random_num}"

def generate_random_past_timestamp(reference_time):
    """Generate a random timestamp within the last 24 hours"""
    minutes_ago = random.randint(1, 24 * 60)  # Random minutes in last 24 hours
    if isinstance(reference_time, str):
        reference_time = datetime.fromisoformat(reference_time)
    past_time = reference_time - timedelta(minutes=minutes_ago)
    return past_time.isoformat()

def generate_random_future_timestamp(reference_time):
    """Generate a random timestamp 1-224 minutes after the reference time"""
    minutes_ahead = random.randint(1, 224)  # Random minutes up to 224 minutes ahead
    if isinstance(reference_time, str):
        reference_time = datetime.fromisoformat(reference_time)
    future_time = reference_time + timedelta(minutes=minutes_ahead)
    return future_time.isoformat()

def load_topics():
    with open('topics.json', 'r', encoding='utf-8') as f:
        return set(json.load(f))

def extract_topic_from_content(content, available_topics):
    # Convert content to uppercase since topics are in uppercase
    content_upper = content.upper()
    
    # Try to find any topic mention in the content
    for topic in available_topics:
        if topic in content_upper:
            return topic
            
    # If no direct match found, look for common stock variations
    # Remove common prefixes/suffixes that might appear in content
    content_words = set(re.findall(r'\b[A-Z0-9]+\b', content_upper))
    for topic in available_topics:
        base_topic = re.sub(r'(LTD|LIMITED|INDIA|&CO)$', '', topic)
        if base_topic.strip() in content_words:
            return topic
            
    # Default to NIFTY if no match found
    return "NIFTY"

def create_formatted_output(post_content, post_author, comments, forced_topic=None):
    try:
        now = datetime.now(timezone.utc)
        
        # Create a shorter title from the content as fallback (but will be overwritten by generated title)
        # Ensure this fallback is plain text with no HTML
        import re as _re
        _fallback_title = post_content.split('.')[0].strip() if post_content else "No title"
        # Strip HTML tags from fallback
        _fallback_title = _re.sub(r'<[^>]*>', '', _fallback_title or '')
        _fallback_title = _re.sub(r'\s+', ' ', _fallback_title).strip()
        if len(_fallback_title) > 150:
            _trimmed = _fallback_title[:150].rstrip()
            _last_space = _trimmed.rfind(' ')
            _fallback_title = _trimmed if _last_space == -1 or _last_space < 20 else _trimmed[:_last_space]
        
        # Use forced_topic if provided, otherwise extract from content
        topic = forced_topic if forced_topic else extract_topic_from_content(post_content, load_topics())
        
        # Generate all timestamps as ISO format strings
        post_time = now - timedelta(minutes=random.randint(1, 24 * 60))
        
        output = {
            "posts": [{
                "temp_post_id": generate_temp_id("post", 1),
                "title": _fallback_title,
                "content": post_content,
                "topic": topic,
                "username": post_author,
                "created_at": post_time.isoformat(),
                "comments": []
            }]
        }
        
        # Add comments with proper format, ensuring timestamps are sequential
        last_time = post_time
        formatted_comments = []
        
        for idx, comment in enumerate(comments, 1):
            next_time = last_time + timedelta(minutes=random.randint(1, 224))
            formatted_comment = {
                "temp_comment_id": generate_temp_id("comment", idx),
                "body": comment["reply"],
                "username": comment["author"],
                "created_at": next_time.isoformat()
            }
            formatted_comments.append(formatted_comment)
            last_time = next_time
        
        output["posts"][0]["comments"] = formatted_comments
        return output
        
    except Exception as e:
        raise Exception(f"Error formatting output: {str(e)}")

def process_article(url, forced_topic=None):
    """Process a single article URL and return the generated post data"""
    print(f"[MAIN] Starting process_article for URL: {url}")
    print(f"[MAIN] Forced topic: {forced_topic}")
    
    # Check cache first
    if forced_topic:
        print(f"[MAIN] Checking cache for URL: {url}, Topic: {forced_topic}")
        cached_post = db.get_generated_post(url, forced_topic)
        if cached_post:
            print(f"[MAIN] Found cached post, returning cached result")
            return cached_post['output']
        else:
            print(f"[MAIN] No cached post found")
    
    # Load personas
    print(f"[MAIN] Loading personas...")
    try:
        with open('personas.json', 'r', encoding='utf-8') as f:
            personas = json.load(f)
        print(f"[MAIN] Loaded {len(personas)} personas")
    except Exception as e:
        print(f"[MAIN] ERROR loading personas: {e}")
        return {
            "error": "persona_load_failed",
            "message": f"Failed to load personas: {str(e)}",
            "url": url
        }

    print(f"[MAIN] Extracting article from URL...")
    article = extract_article(url)
    
    if not article:
        print(f"[MAIN] ERROR: Article extraction failed")
        return {
            "error": "article_extraction_failed",
            "message": "Failed to extract article content",
            "url": url
        }
    
    print(f"[MAIN] Article extracted - Title: {article.get('title', 'No title')[:50]}...")
    print(f"[MAIN] Article text length: {len(article.get('text', ''))} chars")

    persona = random.choice(personas)  # Pick a random persona
    print(f"[MAIN] Selected persona: {persona['name']} ({persona['style']})")
    
    print(f"[MAIN] Calling generate_post...")
    generated_post = generate_post(article['title'], article['text'], persona)
    
    if not generated_post:
        print(f"[MAIN] ERROR: generate_post returned None")
        return {
            "error": "post_generation_failed",
            "message": "Failed to generate post using OpenRouter API",
            "url": url
        }
    
    print(f"[MAIN] Post generated successfully")
    print(f"[MAIN] Generated post keys: {list(generated_post.keys()) if isinstance(generated_post, dict) else 'Not a dict'}")
    
    # Extract title and content from the generated post
    title = generated_post['title']
    content = generated_post['content']

    # Strictly enforce plain-text titles: strip any HTML/markup and normalize whitespace
    try:
        # Remove any HTML tags
        title = re.sub(r'<[^>]*>', '', title or '')
        # Decode common HTML entities we expect to see (avoid escaping issues)
        entity_map = {
            "<": "<",
            ">": ">",
            "&": "&",
            '"': '"',
            "'": "'"
        }
        for k, v in entity_map.items():
            title = title.replace(k, v)
        # After decoding, remove any residual angle brackets to be safe
        title = title.replace('<', '').replace('>', '')
        # Collapse whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        # Enforce 150-char hard limit without cutting mid-word when possible
        if len(title) > 150:
            trimmed = title[:150].rstrip()
            last_space = trimmed.rfind(' ')
            title = trimmed if last_space == -1 or last_space < 20 else trimmed[:last_space]
    except Exception:
        title = (title or '').replace('<', '').replace('>', '').strip()
    
    # Collect replies
    # Select up to 5 unique personas for commenting, excluding the original poster
    num_comments_to_generate = 5
    available_commenters = [p for p in personas if p['name'] != persona['name']]
    replying_bots = random.sample(available_commenters, min(len(available_commenters), num_comments_to_generate))
    comments = []
    
    for bot in replying_bots:
        reply = generate_reply(content, bot)
        comments.append({
            "author": bot['name'],
            "reply": reply
        })

    # Format according to schema, using forced_topic if provided
    output = create_formatted_output(
        post_content=content,
        post_author=persona['name'],
        comments=comments,
        forced_topic=forced_topic
    )
    
    # Save to cache
    if forced_topic:
        db.save_generated_post(url, forced_topic, output)
    
    return output

if __name__ == '__main__':
    # Test URL
    url = "https://www.moneycontrol.com/news/business/markets/dreamfolks-falls-5-as-motilal-oswal-bajaj-finance-turn-sellers-amid-sustained-pressure-on-stock-13236498.html"
    
    output = process_article(url)
    
    if output:
        # Write to output file
        with open('output.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print("✅ Generated post and replies saved to output.json")
    else:
        print("❌ Article failed to extract.")
