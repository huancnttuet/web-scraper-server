#!/bin/bash
# Script to create Lambda Layer for web scraping dependencies
# Run this script in WSL, Linux, or macOS

set -e

echo "Creating dependencies layer for web scraper..."

# Create temp directory
rm -rf layer
mkdir -p layer/python
cd layer

# Install dependencies
echo "Installing dependencies..."
pip install requests beautifulsoup4 lxml -t python --platform manylinux2014_x86_64 --only-binary=:all:

# Create zip file
echo "Creating zip file..."
zip -r dependencies.zip python

echo ""
echo "Layer package created: layer/dependencies.zip"
echo ""
echo "Next steps:"
echo "1. Upload dependencies.zip to S3:"
echo "   aws s3 cp dependencies.zip s3://your-bucket/layers/dependencies.zip"
echo ""
echo "2. Or create layer directly:"
echo "   aws lambda publish-layer-version \\"
echo "     --layer-name web-scraper-dependencies \\"
echo "     --zip-file fileb://dependencies.zip \\"
echo "     --compatible-runtimes python3.12"

cd ..
