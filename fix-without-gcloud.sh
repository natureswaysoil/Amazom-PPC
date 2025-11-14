#!/bin/bash
#
# Instructions for fixing Cloud Run Job when gcloud is not available
# This script just displays instructions since gcloud CLI is not installed
#

cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   ⚠️  GCLOUD CLI NOT AVAILABLE                                        ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝

The gcloud CLI is not installed in this environment.
To fix your Cloud Run Job, you have TWO options:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 OPTION 1: Use Google Cloud Console (Web Interface)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://console.cloud.google.com/run/jobs
2. Find and click: natureswaysoil-video-job
3. Click "EDIT" button
4. Go to "Variables & Secrets" tab
5. Find CSV_URL and click edit
6. Change the URL format to:
   https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0
7. Click "DEPLOY"

✅ No command line required!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🖥️  OPTION 2: Use Google Cloud Shell
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://console.cloud.google.com
2. Click the Cloud Shell icon (>_) in the top right
3. Run this command (replace YOUR_SHEET_ID):

   gcloud run jobs update natureswaysoil-video-job \
     --region=us-east4 \
     --set-env-vars CSV_URL="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv&gid=0"

4. Test the fix:

   gcloud run jobs execute natureswaysoil-video-job \
     --region=us-east4 --wait

✅ Cloud Shell has gcloud pre-installed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Finding Your Sheet ID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

From your Google Sheets URL:
https://docs.google.com/spreadsheets/d/[YOUR_SHEET_ID]/edit#gid=0
                                       ^^^^^^^^^^^^^^^
                                       Copy this part

Example:
URL:      https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H/edit
Sheet ID: 1A2B3C4D5E6F7G8H

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 Complete Instructions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For detailed step-by-step instructions, see:

  cat CLOUDRUN_FIX_NO_GCLOUD.md

This guide includes:
  • Screenshots and detailed console steps
  • Complete command examples
  • Troubleshooting tips
  • Verification steps

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Quick Tip: Your Sheet is Already Public!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You mentioned your Google Sheet is already public, so you ONLY need to:
  ✓ Update the CSV_URL to use /export?format=csv format
  ✓ No permission changes needed!

The fix should take less than 2 minutes using the Console.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

# Check if we're in a terminal and can show the file
if [ -t 1 ]; then
    echo ""
    read -p "Press Enter to view detailed instructions (or Ctrl+C to exit)..."
    echo ""
    if [ -f "CLOUDRUN_FIX_NO_GCLOUD.md" ]; then
        cat CLOUDRUN_FIX_NO_GCLOUD.md | head -n 100
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Full documentation: CLOUDRUN_FIX_NO_GCLOUD.md"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    fi
fi
