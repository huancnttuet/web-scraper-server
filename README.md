# Web Scraper Lambda - Project Files

## 📁 Project Structure

```
lab07-web-scraper/
├── .github/
│   └── workflows/
│       └── deploy-scraper.yml      # GitHub Actions CI/CD workflow
├── lambda/
│   └── scraper_handler.py          # Main Lambda function
├── scripts/
│   ├── create-layer.bat            # Windows script for Lambda Layer
│   ├── create-layer.sh             # Linux/WSL script for Lambda Layer
│   └── deploy.bat                  # Manual deployment script
├── tests/
│   └── test-event.json             # Test event for Lambda
├── template.yaml                   # CloudFormation template (optional)
├── LAB-07-web-scraper.md          # Lab documentation
└── README.md                       # This file
```

## 🚀 Quick Start

### 1. Create Resources via AWS Console

Follow **Part 4** in `LAB-07-web-scraper.md`:

- Create Lambda Layer
- Create DynamoDB Table
- Create S3 Bucket
- Create IAM Role
- Create Lambda Function

### 2. Setup CI/CD with GitHub Actions

1. **Create GitHub repository:**

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/web-scraper-lambda.git
git push -u origin main
```

2. **Add GitHub Secrets:**

   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

3. **Deploy automatically:**

```bash
# Edit code
code lambda/scraper_handler.py

# Push to trigger deployment
git add .
git commit -m "Update scraper logic"
git push
```

## 🧪 Testing

### Test locally with AWS CLI:

```powershell
aws lambda invoke `
    --function-name WebScraper-dev `
    --payload file://tests/test-event.json `
    response.json

cat response.json
```

### Test via GitHub Actions:

1. Go to **Actions** tab
2. Select **Deploy Web Scraper Lambda**
3. Click **Run workflow**

## 🎯 Customization

Edit `lambda/scraper_handler.py` → `parse_html()` function:

```python
# Example: Extract specific content
def parse_html(html_content, url):
    soup = BeautifulSoup(html_content, 'lxml')

    # Your custom selectors here
    items = []
    for element in soup.select('.your-selector'):
        items.append({
            'title': element.select_one('.title').get_text(),
            'link': element.select_one('a')['href']
        })

    return {'items': items, 'url': url}
```

## 📊 Monitor Results

- **S3:** Check `scrapes/YYYY/MM/DD/` folders
- **DynamoDB:** Query `ScraperMetadata-dev` table
- **CloudWatch Logs:** `/aws/lambda/WebScraper-dev`

## 🔧 Dependencies

Lambda Layer includes:

- `requests` - HTTP library
- `beautifulsoup4` - HTML parser
- `lxml` - XML/HTML parser (fast)

## 📚 Resources

- [Lab Documentation](LAB-07-web-scraper.md)
- [BeautifulSoup Docs](https://www.crummy.com/software/BeautifulSoup/)
- [Lambda Layers Guide](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html)
