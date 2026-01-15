@echo off
REM Deploy Lambda function code

set FUNCTION_NAME=web-scraper-scraper
set ZIP_FILE=function.zip

echo Packaging Lambda function...
cd lambda
powershell Compress-Archive -Path *.py -DestinationPath ..\%ZIP_FILE% -Force
cd ..

echo Deploying to Lambda...
aws lambda update-function-code ^
    --function-name %FUNCTION_NAME% ^
    --zip-file fileb://%ZIP_FILE%

echo.
echo Deployment complete!
echo.

REM Cleanup
del %ZIP_FILE%
