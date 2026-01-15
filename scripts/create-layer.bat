@echo off
REM Script to create Lambda Layer for web scraping dependencies
REM Run this script in WSL or Git Bash (requires Linux environment for pip --platform)

echo Creating dependencies layer for web scraper...

REM Create temp directory
mkdir layer\python 2>nul
cd layer

REM Install dependencies (run this in WSL/Linux for correct platform)
echo Installing dependencies...
pip install requests beautifulsoup4 lxml -t python --platform manylinux2014_x86_64 --only-binary=:all:

REM Create zip file
echo Creating zip file...
powershell Compress-Archive -Path python -DestinationPath dependencies.zip -Force

echo.
echo Layer package created: layer\dependencies.zip
echo.
echo Next steps:
echo 1. Upload dependencies.zip to S3:
echo    aws s3 cp dependencies.zip s3://your-bucket/layers/dependencies.zip
echo.
echo 2. Or create layer directly:
echo    aws lambda publish-layer-version ^
echo      --layer-name web-scraper-dependencies ^
echo      --zip-file fileb://dependencies.zip ^
echo      --compatible-runtimes python3.12

cd ..
