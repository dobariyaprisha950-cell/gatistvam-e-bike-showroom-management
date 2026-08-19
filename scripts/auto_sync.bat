@echo off

cd /d E:\Showroom_Project

set BRANCH_CODE=BR-JUN-001
set BRANCH_API_URL_BR-JUN-001=http://127.0.0.1:8000
set BRANCH_API_TOKEN_BR-JUN-001=59c644334c3aeec40bfe655c151b92e0a01827c9

E:\Showroom_Project\myenv\Scripts\python.exe manage.py sync_pending >> E:\Showroom_Project\sync.log 2>&1