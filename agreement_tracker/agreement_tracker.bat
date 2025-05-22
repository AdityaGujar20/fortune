@echo off
REM Start Flask app and open browser automatically

REM Set environment variables
set FLASK_APP=app.py
set FLASK_ENV=production

REM Launch browser (adjust the port if needed)
start "" http://127.0.0.1:5000

REM Start Flask app (no terminal stays open after closing app)
python app.py
exit
