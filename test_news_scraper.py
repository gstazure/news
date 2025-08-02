import csv
from news_scraper import extract_article

# Read URLs from test_articles.csv
with open('test_articles.csv', 'r') as file:
    reader = csv.DictReader(file)
    for row in reader:
        topic = row['topic']
        url = row['url']
        print(f"Extracting article for topic: {topic}")
        print(f"URL: {url}")
        result = extract_article(url)
        if result:
            print(f"Title: {result['title']}")
            print(f"Text preview: {result['text'][:200]}...")
        else:
            print("Failed to extract article")
        print("-" * 50)