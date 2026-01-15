# LAB-07: Web Scraping with Lambda - Clone Data from Website

## 🎯 Objectives

Xây dựng Lambda function để scrape (clone) data từ website và lưu vào S3/DynamoDB:

- Sử dụng Lambda để fetch HTML từ website
- Parse HTML và extract data cần thiết
- Lưu data vào S3 (JSON/CSV) hoặc DynamoDB
- Schedule tự động chạy với EventBridge
- Handle errors và rate limiting

## ⏱️ Estimated Time

90-120 minutes

## 💰 Cost

$0 - Free Tier covers tất cả

## 📋 Prerequisites

- Completed LAB-01 (Lambda basics)
- Hiểu cơ bản về HTML/CSS selectors
- Python cơ bản

---

## 🏗️ Architecture

```
┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│  EventBridge │────▶│   Lambda    │────▶│     S3      │
│  (Schedule)  │     │  (Scraper)  │     │  (Storage)  │
└──────────────┘     └──────┬──────┘     └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │  DynamoDB   │
                     │ (Metadata)  │
                     └─────────────┘
```

**Flow:**

1. EventBridge trigger Lambda theo schedule (mỗi giờ/ngày)
2. Lambda fetch HTML từ target website
3. Parse HTML, extract data
4. Save to S3 (raw data) và DynamoDB (structured data)

---

## ⚠️ Important Notes

### Legal Considerations

- ✅ Chỉ scrape public data
- ✅ Tuân thủ robots.txt của website
- ✅ Không scrape quá nhanh (rate limiting)
- ❌ Không scrape data có bản quyền
- ❌ Không bypass authentication

### robots.txt Check

```python
import urllib.robotparser

rp = urllib.robotparser.RobotFileParser()
rp.set_url("https://example.com/robots.txt")
rp.read()
can_fetch = rp.can_fetch("*", "/page-to-scrape")
```

---

## 📂 Part 1: Project Setup

### Step 1: Create Project Structure

```cmd
cd c:\Users\huan.pl\Desktop\aws\02-lambda
mkdir lab07-web-scraper
cd lab07-web-scraper
mkdir lambda
mkdir cloudformation
```

### Step 2: Create Lambda Layer for Dependencies

Lambda cần thêm libraries như `requests` và `beautifulsoup4`. Tạo layer:

```cmd
mkdir python
pip install requests beautifulsoup4 lxml -t python/
```

Zip layer:

```powershell
Compress-Archive -Path python -DestinationPath scraper-layer.zip
```

---

## 🐍 Part 2: Create Scraper Lambda Function

### Step 1: Create Main Handler

Create file: `lambda/scraper_handler.py`

```python
import json
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
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Request error: {str(e)}")
        return None


def parse_html(html_content, url):
    """
    Parse HTML and extract data

    Customize this function based on your target website structure
    """
    soup = BeautifulSoup(html_content, 'lxml')

    # Example: Extract page title
    title = soup.title.string if soup.title else 'No title'

    # Example: Extract all links
    links = []
    for a in soup.find_all('a', href=True):
        links.append({
            'text': a.get_text(strip=True),
            'href': a['href']
        })

    # Example: Extract all images
    images = []
    for img in soup.find_all('img', src=True):
        images.append({
            'src': img['src'],
            'alt': img.get('alt', '')
        })

    # Example: Extract article/product items (customize selectors)
    items = []

    # For blog articles
    for article in soup.find_all('article'):
        item = {
            'title': '',
            'description': '',
            'link': ''
        }

        # Try to find title
        h2 = article.find(['h1', 'h2', 'h3'])
        if h2:
            item['title'] = h2.get_text(strip=True)

        # Try to find description
        p = article.find('p')
        if p:
            item['description'] = p.get_text(strip=True)[:200]

        # Try to find link
        a = article.find('a', href=True)
        if a:
            item['link'] = a['href']

        if item['title']:
            items.append(item)

    # For product listings (e-commerce)
    for product in soup.find_all(class_=['product', 'product-item', 'item']):
        item = {
            'name': '',
            'price': '',
            'image': '',
            'link': ''
        }

        # Product name
        name = product.find(class_=['product-name', 'product-title', 'title'])
        if name:
            item['name'] = name.get_text(strip=True)

        # Price
        price = product.find(class_=['price', 'product-price'])
        if price:
            item['price'] = price.get_text(strip=True)

        # Image
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
        'links': links[:50],  # Limit to first 50
        'images': images[:50]
    }


def save_to_s3(data, url):
    """Save scraped data to S3 as JSON"""
    if not BUCKET_NAME:
        print("No S3 bucket configured, skipping S3 save")
        return None

    timestamp = datetime.utcnow().strftime('%Y/%m/%d/%H%M%S')
    # Create safe filename from URL
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
```

---

## ☁️ Part 3: CloudFormation Template

### Create Infrastructure Template

Create file: `cloudformation/scraper-stack.yaml`

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Web Scraper Lambda with S3 and DynamoDB

Parameters:
  EnvironmentName:
    Type: String
    Default: dev
  TargetUrl:
    Type: String
    Default: https://example.com
    Description: Default URL to scrape

Resources:
  # S3 Bucket for storing scraped data
  ScraperBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub 'web-scraper-data-${AWS::AccountId}-${AWS::Region}'
      LifecycleConfiguration:
        Rules:
          - Id: DeleteOldData
            Status: Enabled
            ExpirationInDays: 30

  # DynamoDB Table for metadata
  ScraperTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub 'ScraperMetadata-${EnvironmentName}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: url
          AttributeType: S
        - AttributeName: scraped_at
          AttributeType: S
      KeySchema:
        - AttributeName: url
          KeyType: HASH
        - AttributeName: scraped_at
          KeyType: RANGE

  # IAM Role for Lambda
  ScraperRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub 'WebScraperRole-${EnvironmentName}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: ScraperPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:PutObject
                  - s3:GetObject
                Resource: !Sub '${ScraperBucket.Arn}/*'
              - Effect: Allow
                Action:
                  - dynamodb:PutItem
                  - dynamodb:GetItem
                  - dynamodb:Query
                Resource: !GetAtt ScraperTable.Arn

  # Lambda Layer for dependencies
  ScraperLayer:
    Type: AWS::Lambda::LayerVersion
    Properties:
      LayerName: scraper-dependencies
      Description: requests and beautifulsoup4
      Content:
        S3Bucket: !Ref ScraperBucket
        S3Key: layers/scraper-layer.zip
      CompatibleRuntimes:
        - python3.12

  # Lambda Function
  ScraperFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub 'WebScraper-${EnvironmentName}'
      Runtime: python3.12
      Handler: scraper_handler.lambda_handler
      Role: !GetAtt ScraperRole.Arn
      Timeout: 60
      MemorySize: 512
      Layers:
        - !Ref ScraperLayer
      Environment:
        Variables:
          BUCKET_NAME: !Ref ScraperBucket
          TABLE_NAME: !Ref ScraperTable
          TARGET_URL: !Ref TargetUrl
      Code:
        ZipFile: |
          # Placeholder - upload actual code
          def lambda_handler(event, context):
              return {'statusCode': 200, 'body': 'Placeholder'}

  # EventBridge Rule for scheduled execution
  ScraperSchedule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub 'WebScraperSchedule-${EnvironmentName}'
      Description: Run web scraper every hour
      ScheduleExpression: rate(1 hour)
      State: DISABLED # Enable when ready
      Targets:
        - Id: ScraperTarget
          Arn: !GetAtt ScraperFunction.Arn

  # Permission for EventBridge to invoke Lambda
  ScraperSchedulePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref ScraperFunction
      Action: lambda:InvokeFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt ScraperSchedule.Arn

Outputs:
  FunctionName:
    Value: !Ref ScraperFunction
  BucketName:
    Value: !Ref ScraperBucket
  TableName:
    Value: !Ref ScraperTable
```

---

## 🖥️ Part 4: Deploy via Console

### Step 1: Create Lambda Layer

1. **Lambda Console** → **Layers** → **Create layer**
2. **Name:** `scraper-dependencies`
3. **Upload:** `scraper-layer.zip`
4. **Compatible runtimes:** Python 3.12
5. Click **Create**

### Step 2: Create DynamoDB Table

1. **DynamoDB Console** → **Create table**
2. **Table name:** `ScraperMetadata-dev`
3. **Partition key:** `url` (String)
4. **Sort key:** `scraped_at` (String)
5. **Table settings:** Default
6. Click **Create table**

### Step 3: Create S3 Bucket

1. **S3 Console** → **Create bucket**
2. **Bucket name:** `web-scraper-data-YOUR_ACCOUNT_ID`
3. **Region:** Same as Lambda
4. Click **Create bucket**

### Step 4: Create IAM Role

1. **IAM Console** → **Roles** → **Create role**
2. **Trusted entity:** AWS service → Lambda
3. **Permissions:**
   - `AWSLambdaBasicExecutionRole`
   - Custom inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::web-scraper-data-*/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query"],
      "Resource": "arn:aws:dynamodb:*:*:table/ScraperMetadata-*"
    }
  ]
}
```

4. **Role name:** `WebScraperRole`
5. Click **Create role**

### Step 5: Create Lambda Function

1. **Lambda Console** → **Create function**
2. **Function name:** `WebScraper-dev`
3. **Runtime:** Python 3.12
4. **Execution role:** Use existing role → `WebScraperRole`
5. Click **Create function**

6. **Add Layer:**

   - Scroll to Layers → **Add a layer**
   - **Custom layers** → Select `scraper-dependencies`
   - Click **Add**

7. **Configuration:**

   - **General:** Timeout = 60 seconds, Memory = 512 MB
   - **Environment variables:**
     - `BUCKET_NAME` = `web-scraper-data-YOUR_ACCOUNT_ID`
     - `TABLE_NAME` = `ScraperMetadata-dev`
     - `TARGET_URL` = `https://example.com`

8. **Code:** Paste code from `scraper_handler.py`

9. Click **Deploy**

---

## 🧪 Part 5: Testing

### Test 1: Direct Invocation

1. **Lambda Console** → **WebScraper-dev** → **Test**
2. **Event JSON:**

```json
{
  "url": "https://news.ycombinator.com/"
}
```

3. Click **Test**
4. Check:
   - ✅ Lambda returns 200
   - ✅ S3 has new JSON file
   - ✅ DynamoDB has new record

### Test 2: Different Website

```json
{
  "url": "https://www.python.org/"
}
```

### Test 3: CLI Invocation

```powershell
aws lambda invoke `
    --function-name WebScraper-dev `
    --payload '{\"url\": \"https://example.com\"}' `
    response.json

cat response.json
```

---

## ⏰ Part 6: Schedule with EventBridge

### Create Schedule Rule

1. **EventBridge Console** → **Rules** → **Create rule**
2. **Name:** `WebScraperSchedule`
3. **Rule type:** Schedule
4. **Schedule pattern:**
   - **Rate-based:** `rate(1 hour)` - Mỗi giờ
   - Hoặc **Cron-based:** `cron(0 9 * * ? *)` - Mỗi ngày 9h sáng UTC
5. **Target:** Lambda function → `WebScraper-dev`
6. Click **Create rule**

### Schedule Expressions

| Expression                | Meaning              |
| ------------------------- | -------------------- |
| `rate(1 hour)`            | Every hour           |
| `rate(6 hours)`           | Every 6 hours        |
| `rate(1 day)`             | Every day            |
| `cron(0 12 * * ? *)`      | Daily at 12:00 UTC   |
| `cron(0 8 ? * MON-FRI *)` | Weekdays at 8:00 UTC |

---

## 🚀 Part 7: CI/CD with GitHub Actions

### Step 1: Setup GitHub Repository

1. **Create GitHub repository** cho project
2. **Push code lên GitHub:**

```powershell
cd c:\Users\huan.pl\Desktop\aws\02-lambda\lab07-web-scraper
git init
git add .
git commit -m "Initial commit - Web Scraper Lambda"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/web-scraper-lambda.git
git push -u origin main
```

### Step 2: Configure GitHub Secrets

1. **GitHub Repository** → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add secrets:

| Name                    | Value               | Description          |
| ----------------------- | ------------------- | -------------------- |
| `AWS_ACCESS_KEY_ID`     | Your AWS Access Key | IAM user credentials |
| `AWS_SECRET_ACCESS_KEY` | Your AWS Secret Key | IAM user credentials |

### Step 3: Create GitHub Actions Workflow

File đã có sẵn: `.github/workflows/deploy-scraper.yml`

```yaml
name: Deploy Web Scraper Lambda

on:
  push:
    branches:
      - main
      - master
    paths:
      - '02-lambda/lab07-web-scraper/lambda/**'
      - '.github/workflows/deploy-scraper.yml'
  workflow_dispatch:

env:
  AWS_REGION: us-east-1
  FUNCTION_NAME: WebScraper-dev

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Create deployment package
        working-directory: 02-lambda/lab07-web-scraper
        run: |
          cd lambda
          zip -r ../function.zip *.py

      - name: Deploy Lambda function
        working-directory: 02-lambda/lab07-web-scraper
        run: |
          aws lambda update-function-code \
            --function-name ${{ env.FUNCTION_NAME }} \
            --zip-file fileb://function.zip \
            --region ${{ env.AWS_REGION }}

      - name: Wait for update to complete
        run: |
          aws lambda wait function-updated-v2 \
            --function-name ${{ env.FUNCTION_NAME }} \
            --region ${{ env.AWS_REGION }}

      - name: Update environment variables (optional)
        run: |
          aws lambda update-function-configuration \
            --function-name ${{ env.FUNCTION_NAME }} \
            --timeout 60 \
            --memory-size 512 \
            --region ${{ env.AWS_REGION }}

      - name: Test function
        run: |
          aws lambda invoke \
            --function-name ${{ env.FUNCTION_NAME }} \
            --payload '{"url": "https://example.com"}' \
            --region ${{ env.AWS_REGION }} \
            response.json

          cat response.json

      - name: Deployment summary
        run: |
          echo "✅ Lambda function deployed successfully!"
          echo "Function: ${{ env.FUNCTION_NAME }}"
          echo "Region: ${{ env.AWS_REGION }}"
```

### Step 4: Deploy via GitHub Actions

**Option 1: Auto deploy on push**

```powershell
# Edit code
code lambda\scraper_handler.py

# Commit and push
git add .
git commit -m "Update scraper logic"
git push origin main

# GitHub Actions sẽ tự động deploy
```

**Option 2: Manual trigger**

1. **GitHub** → **Actions** → **Deploy Web Scraper Lambda**
2. Click **Run workflow** → **Run workflow**
3. Xem deployment progress

### Step 5: Monitor Deployment

1. **GitHub** → **Actions** tab
2. Click vào workflow run để xem logs
3. Check từng step:
   - ✅ Checkout code
   - ✅ Configure AWS credentials
   - ✅ Create deployment package
   - ✅ Deploy Lambda function
   - ✅ Test function

### Workflow Features

| Feature            | Description                                   |
| ------------------ | --------------------------------------------- |
| **Auto trigger**   | Deploy khi push code thay đổi trong `lambda/` |
| **Manual trigger** | `workflow_dispatch` cho manual deployment     |
| **Path filter**    | Chỉ deploy khi Lambda code thay đổi           |
| **Function test**  | Auto test sau khi deploy                      |
| **Wait mechanism** | Đợi Lambda update complete trước khi test     |

---

## 🎯 Part 8: Customize for Your Use Case

### Example 1: News Headlines Scraper

```python
def parse_news_site(html_content):
    soup = BeautifulSoup(html_content, 'lxml')

    headlines = []
    for item in soup.select('.headline, .news-item, article h2'):
        headlines.append({
            'title': item.get_text(strip=True),
            'link': item.find_parent('a')['href'] if item.find_parent('a') else ''
        })

    return headlines
```

### Example 2: E-commerce Price Tracker

```python
def parse_product_prices(html_content):
    soup = BeautifulSoup(html_content, 'lxml')

    products = []
    for product in soup.select('.product-card'):
        name = product.select_one('.product-name')
        price = product.select_one('.price')

        products.append({
            'name': name.get_text(strip=True) if name else '',
            'price': price.get_text(strip=True) if price else '',
            'timestamp': datetime.utcnow().isoformat()
        })

    return products
```

### Example 3: Job Listings Scraper

```python
def parse_job_listings(html_content):
    soup = BeautifulSoup(html_content, 'lxml')

    jobs = []
    for job in soup.select('.job-listing, .job-card'):
        title = job.select_one('.job-title, h2')
        company = job.select_one('.company-name')
        location = job.select_one('.location')

        jobs.append({
            'title': title.get_text(strip=True) if title else '',
            'company': company.get_text(strip=True) if company else '',
            'location': location.get_text(strip=True) if location else ''
        })

    return jobs
```

---

## 🧹 Part 9: Cleanup

### Via Console

1. **EventBridge Console:**

   - Rules → Select `WebScraperSchedule` → Delete

2. **Lambda Console:**

   - Functions → Select `WebScraper-dev` → Actions → Delete
   - Layers → Select `scraper-dependencies` → Delete

3. **DynamoDB Console:**

   - Tables → Select `ScraperMetadata-dev` → Delete

4. **S3 Console:**

   - Buckets → Select `web-scraper-data-*`
   - Empty bucket → Delete bucket

5. **IAM Console:**
   - Roles → Select `WebScraperRole`
   - Delete inline policies → Delete role

### Via CLI

```powershell
# Delete EventBridge rule
aws events remove-targets --rule WebScraperSchedule --ids ScraperTarget
aws events delete-rule --name WebScraperSchedule

# Delete Lambda function
aws lambda delete-function --function-name WebScraper-dev

# Delete Lambda layer
aws lambda delete-layer-version --layer-name scraper-dependencies --version-number 1

# Delete DynamoDB table
aws dynamodb delete-table --table-name ScraperMetadata-dev

# Empty and delete S3 bucket
aws s3 rm s3://web-scraper-data-YOUR_ACCOUNT_ID --recursive
aws s3 rb s3://web-scraper-data-YOUR_ACCOUNT_ID

# Delete IAM role policies
aws iam delete-role-policy --role-name WebScraperRole --policy-name ScraperPolicy
aws iam detach-role-policy --role-name WebScraperRole --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name WebScraperRole
```

---

## ✅ Lab Checklist

**Setup (AWS Console)**

- [ ] Created Lambda layer with dependencies (`requests`, `beautifulsoup4`, `lxml`)
- [ ] Created S3 bucket for storing scraped data
- [ ] Created DynamoDB table for metadata
- [ ] Created IAM role with S3 + DynamoDB permissions
- [ ] Created Lambda function with layer attached
- [ ] Configured environment variables (BUCKET_NAME, TABLE_NAME, TARGET_URL)

**Testing**

- [ ] Tested direct invocation from Lambda Console
- [ ] Verified S3 has JSON files
- [ ] Verified DynamoDB has records
- [ ] Tested different URLs

**Automation**

- [ ] Created EventBridge schedule rule
- [ ] Verified scheduled execution works

**CI/CD (GitHub Actions)**

- [ ] Created GitHub repository
- [ ] Added AWS credentials to GitHub Secrets
- [ ] Created `.github/workflows/deploy-scraper.yml`
- [ ] Tested auto-deployment on code push
- [ ] Tested manual workflow trigger

**Customization**

- [ ] Customized `parse_html()` for target website
- [ ] Updated CSS selectors for specific content
- [ ] Tested with real target website

**Cleanup**

- [ ] Deleted all AWS resources
- [ ] Verified no charges in billing dashboard

---

## 🎓 Key Takeaways for SAA Exam

1. **Lambda Layers** - Share code/dependencies across functions
2. **EventBridge Rules** - Schedule Lambda executions
3. **S3 + Lambda** - Common serverless pattern
4. **DynamoDB** - Fast NoSQL for metadata storage
5. **IAM Least Privilege** - Only grant needed permissions
6. **Lambda Timeout** - Max 15 minutes, plan accordingly

---

## 📚 Additional Resources

- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html)
- [EventBridge Schedule Expressions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-schedule-expressions.html)
- [Web Scraping Best Practices](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/web-scraping.html)
