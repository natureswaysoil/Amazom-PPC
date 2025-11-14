#!/bin/bash
# Quick Start Guide for Cloud Run Job Fix
# Run this script to see all available tools and next steps

cat << 'EOF'
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   Cloud Run Job Fix - Quick Start Guide                       ║
║   Problem: natureswaysoil-video-job timeout                   ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

📋 PROBLEM SUMMARY
──────────────────────────────────────────────────────────────────
Your Cloud Run Job "natureswaysoil-video-job" in us-east4 is 
timing out after 600 seconds due to HTTP 400 "Page Not Found" 
errors when accessing a Google Sheet via CSV_URL.

🚀 QUICK FIX (3 STEPS)
──────────────────────────────────────────────────────────────────

1️⃣  Run Diagnostics (identifies the specific issue)
    
    ./diagnose-cloudrun-job.sh

2️⃣  Apply Automatic Fix (corrects URL format & config)
    
    ./fix-cloudrun-sheet.sh

3️⃣  Test the Job (verify fix worked)
    
    gcloud run jobs execute natureswaysoil-video-job \
      --region=us-east4 --wait


📚 AVAILABLE TOOLS
──────────────────────────────────────────────────────────────────

Scripts:
  • diagnose-cloudrun-job.sh     - Automated diagnostics
  • fix-cloudrun-sheet.sh        - Interactive fix script
  • google_sheet_fetcher.py      - Python utility for app integration

Documentation:
  • README_CLOUDRUN_FIX.md       - Main documentation (START HERE)
  • CLOUDRUN_QUICK_FIX.md        - Quick command reference
  • CLOUD_RUN_GOOGLE_SHEET_FIX.md - Comprehensive guide
  • CLOUDRUN_FIX_SUMMARY.md      - Complete solution summary


🔍 COMMON ISSUES & QUICK FIXES
──────────────────────────────────────────────────────────────────

Issue 1: Wrong URL Format
  Problem: URL uses /edit instead of /export?format=csv
  Fix: Run ./fix-cloudrun-sheet.sh (automatically converts)
  
Issue 2: Permission Denied (HTTP 403)
  Problem: Service account can't access sheet
  Fix: Share sheet with service account email (script provides it)
  
Issue 3: Sheet Not Found (HTTP 404)
  Problem: Wrong sheet ID or sheet deleted
  Fix: Verify sheet exists and get correct ID from URL
  
Issue 4: Still Times Out
  Problem: Application issue, not URL issue
  Fix: Integrate google_sheet_fetcher.py for fast-fail handling


🧪 MANUAL TESTING COMMANDS
──────────────────────────────────────────────────────────────────

Test URL Access:
  curl -L "YOUR_CSV_URL" | head -n 5

Check Job Config:
  gcloud run jobs describe natureswaysoil-video-job \
    --region=us-east4

View Recent Logs:
  gcloud logging read \
    "resource.type=cloud_run_job AND 
     resource.labels.job_name=natureswaysoil-video-job" \
    --limit=50

Test with Python Utility:
  python google_sheet_fetcher.py \
    --url "YOUR_CSV_URL" --preview 10


📖 DETAILED HELP
──────────────────────────────────────────────────────────────────

For comprehensive documentation, read:
  
  cat README_CLOUDRUN_FIX.md

For quick command reference:
  
  cat CLOUDRUN_QUICK_FIX.md

For detailed troubleshooting:
  
  cat CLOUD_RUN_GOOGLE_SHEET_FIX.md


✅ SUCCESS CHECKLIST
──────────────────────────────────────────────────────────────────

After applying fixes, verify:
  □ CSV_URL is in /export?format=csv format
  □ curl returns CSV data (not HTML)
  □ Service account has permissions
  □ Job executes without timeout
  □ Logs show successful data retrieval


🆘 NEED HELP?
──────────────────────────────────────────────────────────────────

1. Run diagnostics first:
   ./diagnose-cloudrun-job.sh

2. Review the output and follow recommendations

3. Read the documentation:
   - README_CLOUDRUN_FIX.md for overview
   - CLOUDRUN_QUICK_FIX.md for commands
   - CLOUD_RUN_GOOGLE_SHEET_FIX.md for details

4. Still stuck? Contact:
   Email: james@natureswaysoil.com
   GitHub: https://github.com/natureswaysoil/Amazom-PPC/issues


🎯 RECOMMENDED NEXT STEP
──────────────────────────────────────────────────────────────────

Start with diagnostics to identify the exact issue:

  ./diagnose-cloudrun-job.sh

The script will check everything and tell you exactly what needs
to be fixed.

╔════════════════════════════════════════════════════════════════╗
║  All tools are ready to use. Start with diagnostics! 🚀       ║
╚════════════════════════════════════════════════════════════════╝

EOF
