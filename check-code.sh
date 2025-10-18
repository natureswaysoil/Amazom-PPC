#!/bin/bash

echo "🔍 Checking Deployed Code"
echo "=========================="
echo ""

# Check what's in the current directory
echo "Files in current directory:"
ls -la main.py optimizer_core.py dashboard_client.py

echo ""
echo "Checking main.py for health endpoint..."
grep -n "health_flag\|Health endpoint" main.py | head -10

echo ""
echo "Current git commit:"
git log --oneline -1

echo ""
echo "============================="
echo ""
echo "If you don't see 'health_flag' or 'Health endpoint' above,"
echo "then main.py in Cloud Shell is outdated."
echo ""
echo "Solution: Make sure you're deploying from a directory that has"
echo "the latest main.py with the health endpoint code."
