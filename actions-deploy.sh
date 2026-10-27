#!/bin/bash

echo "=========================================="
echo "Starting Deployment Process"
echo "=========================================="
echo "Timestamp: $(date)"

# Variables
APP_DIR="/opt/github-actions-jenkins-app"
PYTHON_VERSION="3.9"
PORT="5000"

echo "[1/7] Creating application directory..."
mkdir -p $APP_DIR

echo "[2/7] Pulling latest code from GitHub..."
cd $APP_DIR
git pull origin master 2>&1 || git clone git@github.com:YOUR-USERNAME/github-actions-jenkins-cicd.git . 2>&1

echo "[3/7] Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "[4/7] Running tests before deployment..."
pytest test_app.py -v

if [ $? -ne 0 ]; then
    echo "Tests failed! Deployment aborted."
    exit 1
fi

echo "[5/7] Stopping old application..."
pkill -f "python app.py" || true
sleep 2

echo "[6/7] Starting new application..."
cd $APP_DIR
nohup python app.py > app.log 2>&1 &
APP_PID=$!
echo "Application started with PID: $APP_PID"

echo "[7/7] Verifying deployment..."
sleep 3

# Health check
curl -s http://localhost:$PORT/health
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Deployment Successful!"
    echo "=========================================="
    echo "Application is running on port $PORT"
    echo "Health: $(curl -s http://localhost:$PORT/health)"
else
    echo ""
    echo "=========================================="
    echo "Deployment may have issues - check logs"
    echo "=========================================="
    tail -20 $APP_DIR/app.log
fi
