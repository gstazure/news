from newspaper import Article, Config
import re
from urllib.parse import urlparse
import random
import requests
from bs4 import BeautifulSoup
from database import db  # Import our database module

def get_source_config(url):
    """Get source-specific configuration"""
    domain = urlparse(url).netloc.lower()
    
    configs = {
        'moneycontrol.com': {
            'remove_patterns': [
                r'Follow us on.*$',
                r'Download The Economic Times News App.*$',
                r'Click here to download.*$',
                r'Disclaimer:.*$',
                r'Catch all the Business News.*$',
                r'Also Read:.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        'economictimes.indiatimes.com': {
            'remove_patterns': [
                r'Download The Economic Times News App.*$',
                r'\(This story originally appeared.*\)',
                r'Never miss a great news story!.*$',
                r'Click here to download.*$',
                r'Also Read:.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0'
        },
        'livemint.com': {
            'remove_patterns': [
                r'Download the Mint app.*$',
                r'Click here to read.*$',
                r'Also read:.*$',
                r'Catch all the Business News.*$',
                r'Subscribe to Mint Newsletters.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/89.0'
        },
        'business-standard.com': {
            'remove_patterns': [
                r'Dear Reader,.*$',
                r'Business Standard has always.*$',
                r'Key stories on business-standard.*$',
                r'Subscribe to Business Standard Premium.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/91.0'
        },
        'financialexpress.com': {
            'remove_patterns': [
                r'Get live Share Market updates.*$',
                r'Also read:.*$',
                r'For all the latest.*$',
                r'Subscribe to FE Daily Newsletter.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Safari/537.36'
        },
        'nseindia.com': {
            'remove_patterns': [
                r'Copyright © National Stock Exchange.*$',
                r'Disclaimer:.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0'
        },
        'bseindia.com': {
            'remove_patterns': [
                r'Copyright © BSE.*$',
                r'Disclaimer:.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/89.0'
        },
        'zeebiz.com': {
            'remove_patterns': [
                r'Click here to read.*$',
                r'WATCH ZEE BUSINESS LIVE TV.*$',
                r'Download the Zee Business App.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/91.0'
        },
        'reuters.com': {
            'remove_patterns': [
                r'Reporting by.*$',
                r'Our Standards:.*$',
                r'Register now for.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0'
        },
        'bloombergquint.com': {
            'remove_patterns': [
                r'BQ Prime is now available.*$',
                r'Subscribe to BQ Prime.*$',
                r'Also Read:.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/89.0'
        },
        'thehindubusinessline.com': {
            'remove_patterns': [
                r'Published on.*$',
                r'Subscribe to The Hindu BusinessLine.*$',
                r'Follow us on .*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/91.0'
        },
        'equitymaster.com': {
            'remove_patterns': [
                r'This article is from.*$',
                r'Subscribe to Equitymaster.*$',
                r'Equitymaster Agora Research.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Safari/537.36'
        },
        'tickertape.in': {
            'remove_patterns': [
                r'Download the Tickertape App.*$',
                r'Subscribe to our newsletter.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0'
        },
        'cnbctv18.com': {
            'remove_patterns': [
                r'ALSO READ:.*$',
                r'Follow our live blog.*$',
                r'Disclaimer:.*$',
                r'First Published:.*$'
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/89.0'
        }
    }
    
    # Default config for unknown sources
    default_config = {
        'remove_patterns': [],
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Find matching domain (handle www. and subdomains)
    for known_domain, config in configs.items():
        if known_domain in domain:
            return config
    
    return default_config

def clean_article_text(text, remove_patterns):
    """Clean article text by removing unwanted patterns"""
    cleaned_text = text
    
    # Remove unwanted patterns
    for pattern in remove_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
    
    # General cleanup
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Replace multiple spaces with single space
    cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)  # Remove multiple newlines
    
    return cleaned_text.strip()

def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/114.0.1823.67 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    ]
    return random.choice(user_agents)

def extract_article(url):
    try:
        # Get source-specific configuration
        source_config = get_source_config(url)
        
        # First try with requests and BeautifulSoup
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(url, headers=headers, timeout=15, verify=True)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find the main article content based on common patterns
            article_text = ""
            
            # Look for article content in common containers
            content_selectors = [
                'article', '.article-content', '.story-content',
                '[itemprop="articleBody"]', '.entry-content',
                '#article-content', '.content-body'
            ]
            
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    article_text = content.get_text(separator='\n').strip()
                    break
            
            # If we found content, clean and return it
            if article_text:
                cleaned_text = clean_article_text(article_text, source_config['remove_patterns'])
                
                # Try to find title
                title = ""
                title_selectors = ['h1', '[itemprop="headline"]', '.article-title', '.entry-title']
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text().strip()
                        break
                
                return {
                    "title": title,
                    "text": cleaned_text
                }
        
        # If requests method failed or didn't find content, try newspaper3k as fallback
        config = Config()
        config.browser_user_agent = get_random_user_agent()
        config.request_timeout = 15
        config.fetch_images = False
        
        article = Article(url, config=config)
        article.download()
        article.parse()
        
        cleaned_text = clean_article_text(article.text, source_config['remove_patterns'])
        
        return {
            "title": article.title.strip(),
            "text": cleaned_text
        }
    except Exception as e:
        print(f"Error extracting article: {e}")
        return None
