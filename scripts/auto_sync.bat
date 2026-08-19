@echo off

cd /d E:\Showroom_Project

call E:\Showroom_Project\myenv\Scripts\activate.bat

set "BRANCH_CODE=BR-JUN-001"
set "BRANCH_API_URL_BR-JUN-001=http://127.0.0.1:8000"
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v "BRANCH_API_TOKEN_BR-JUN-001" 2^>nul') do set "BRANCH_API_TOKEN_BR-JUN-001=%%B"

python manage.py sync_pending >> E:\Showroom_Project\sync.log 2>&1

exit /b 0