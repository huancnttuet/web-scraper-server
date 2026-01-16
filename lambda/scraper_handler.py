import json
import uuid
import boto3
import os
from datetime import datetime
from bs4 import BeautifulSoup
import requests

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ.get('BUCKET_NAME', '')
TABLE_NAME = os.environ.get('TABLE_NAME', '')
TARGET_URL = os.environ.get('TARGET_URL', '')

# Headers to mimic browser request
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


def lambda_handler(event, context):
    """
    Main handler for web scraping Lambda
    
    Can be triggered by:
    - EventBridge (scheduled)
    - API Gateway (manual trigger)
    - Direct invocation
    """
    try:
        # Get URL from event or environment
        url = event.get('url', TARGET_URL)
        
        if not url:
            return response(400, {'error': 'No URL provided'})
        
        print(f"Scraping URL: {url}")
        
        # Fetch HTML
        html_content = fetch_page(url)
        
        if not html_content:
            return response(500, {'error': 'Failed to fetch page'})
        
        # Parse and extract data
        data = parse_html(html_content, url)
        
        if not data:
            return response(500, {'error': 'Failed to parse page'})
        
        # Save to S3
        s3_key = save_to_s3(data, url)
        
        # Save to DynamoDB
        save_to_dynamodb(data, url, s3_key)
        
        return response(200, {
            'message': 'Scraping completed successfully',
            'url': url,
            's3_key': s3_key,
            'items_count': len(data.get('items', []))
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return response(500, {'error': str(e)})


def fetch_page(url):
    """Fetch HTML content from URL"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"Request error: {str(e)}")
        return None


def parse_html(html_content, url):
    """
    Parse HTML and extract data
    
    Customize this function based on your target website structure
    """
    soup = BeautifulSoup(html_content, 'lxml')
    
    # Extract page title
    title = soup.title.string if soup.title else 'No title'
    
    # Extract all links
    links = []
    for a in soup.find_all('a', href=True):
        links.append({
            'text': a.get_text(strip=True),
            'href': a['href']
        })
    
    # Extract all images
    images = []
    for img in soup.find_all('img', src=True):
        images.append({
            'src': img['src'],
            'alt': img.get('alt', '')
        })
    
    # Extract article/product items (customize selectors for your target site)
    items = []
    
    # For blog articles
    for article in soup.find_all('article'):
        item = {
            'title': '',
            'description': '',
            'link': ''
        }
        
        h2 = article.find(['h1', 'h2', 'h3'])
        if h2:
            item['title'] = h2.get_text(strip=True)
        
        p = article.find('p')
        if p:
            item['description'] = p.get_text(strip=True)[:200]
        
        a = article.find('a', href=True)
        if a:
            item['link'] = a['href']
        
        if item['title']:
            items.append(item)
    
    # For product listings
    for product in soup.find_all(class_=['product', 'product-item', 'item']):
        item = {
            'name': '',
            'price': '',
            'image': '',
            'link': ''
        }
        
        name = product.find(class_=['product-name', 'product-title', 'title'])
        if name:
            item['name'] = name.get_text(strip=True)
        
        price = product.find(class_=['price', 'product-price'])
        if price:
            item['price'] = price.get_text(strip=True)
        
        img = product.find('img', src=True)
        if img:
            item['image'] = img['src']
        
        if item['name']:
            items.append(item)
    
    return {
        'url': url,
        'title': title,
        'scraped_at': datetime.utcnow().isoformat(),
        'links_count': len(links),
        'images_count': len(images),
        'items': items,
        'links': links[:50],
        'images': images[:50]
    }


def save_to_s3(data, url):
    """Save scraped data to S3 as JSON"""
    if not BUCKET_NAME:
        print("No S3 bucket configured, skipping S3 save")
        return None
    
    timestamp = datetime.utcnow().strftime('%Y/%m/%d/%H%M%S')
    safe_name = url.replace('https://', '').replace('http://', '').replace('/', '_')[:50]
    s3_key = f"scrapes/{timestamp}_{safe_name}.json"
    
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(data, ensure_ascii=False, indent=2),
        ContentType='application/json'
    )
    
    print(f"Saved to S3: {s3_key}")
    return s3_key


def save_to_dynamodb(data, url, s3_key):
    """Save metadata to DynamoDB"""
    if not TABLE_NAME:
        print("No DynamoDB table configured, skipping DynamoDB save")
        return
    
    table = dynamodb.Table(TABLE_NAME)
    
    item = {
        'id': str(uuid.uuid4()),
        'url': url,
        'scraped_at': data['scraped_at'],
        'title': data['title'],
        'items_count': len(data.get('items', [])),
        'links_count': data.get('links_count', 0),
        'images_count': data.get('images_count', 0),
        's3_key': s3_key or 'N/A'
    }
    
    table.put_item(Item=item)
    print(f"Saved to DynamoDB: {url}")


def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }
