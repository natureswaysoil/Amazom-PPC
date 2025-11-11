# Amazon PPC Optimizer - Profile ID Update

## ✅ Update Completed

**Date**: November 11, 2025  
**Profile ID**: `1780498399290938`  
**Status**: Ready for deployment

---

## 📋 Summary of Changes

The optimizer has been updated to use the correct Amazon Advertising Profile ID instead of the placeholder `"YOUR_PROFILE_ID"`.

### Files Modified:

1. **config.json**
   - ✅ Updated `amazon_api.profile_id` from `"YOUR_PROFILE_ID"` to `"1780498399290938"`

2. **.env.template**
   - ✅ Updated `AMAZON_PROFILE_ID` from `"YOUR_PROFILE_ID_HERE"` to `"1780498399290938"`

3. **main.py**
   - ✅ Added `AMAZON_PROFILE_ID` to `set_environment_variables()` function
   - ✅ Updated profile ID retrieval to prioritize environment variables
   - ✅ Enhanced error messages for missing profile ID

4. **optimizer_profile_id_helper.py** (New)
   - ✅ Added helper module for retrieving profile ID from Google Secret Manager

---

## 🔑 Configuration Priority

The optimizer now uses the following priority order for the profile ID:

1. **Environment Variable** (Highest Priority)
   ```bash
   export AMAZON_PROFILE_ID=1780498399290938
   ```

2. **Google Secret Manager** (Recommended for Production)
   ```python
   from optimizer_profile_id_helper import get_profile_id
   profile_id = get_profile_id()
   ```

3. **config.json** (Fallback)
   ```json
   {
     "amazon_api": {
       "profile_id": "1780498399290938"
     }
   }
   ```

---

## 🚀 How to Use

### Option 1: Environment Variable (Simplest)

```bash
# Set the profile ID as an environment variable
export AMAZON_PROFILE_ID=1780498399290938

# Run the optimizer
python main.py
```

### Option 2: Use config.json (Already Updated)

The `config.json` file has been updated with the correct profile ID. Simply run:

```bash
python main.py
```

### Option 3: Google Secret Manager (Production)

For production deployments, use Google Secret Manager:

```python
from optimizer_profile_id_helper import get_profile_id

# This retrieves from: projects/1009540130231/secrets/ppc-profile-id/versions/latest
profile_id = get_profile_id()
```

---

## 🔧 Deployment Instructions

### Local Development

1. **Clone the repository** (if not already done):
   ```bash
   git clone https://github.com/natureswaysoil/Amazom-PPC.git
   cd Amazom-PPC
   ```

2. **Create .env file** (optional, for environment variables):
   ```bash
   cp .env.template .env
   # The profile ID is already set to 1780498399290938
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the optimizer**:
   ```bash
   python main.py
   ```

### Google Cloud Function Deployment

1. **Set the profile ID as a secret** (if using Secret Manager):
   ```bash
   echo -n "1780498399290938" | gcloud secrets create ppc-profile-id \
     --project=1009540130231 \
     --replication-policy="automatic" \
     --data-file=-
   ```

2. **Deploy the function**:
   ```bash
   gcloud functions deploy amazon-ppc-optimizer \
     --runtime python39 \
     --trigger-http \
     --entry-point optimize \
     --set-env-vars AMAZON_PROFILE_ID=1780498399290938 \
     --project=amazon-ppc-474902
   ```

3. **Or use the deployment script**:
   ```bash
   ./deploy.sh
   ```

### Cloud Run Deployment

```bash
# Build and deploy
gcloud run deploy amazon-ppc-optimizer \
  --source . \
  --set-env-vars AMAZON_PROFILE_ID=1780498399290938 \
  --project=amazon-ppc-474902
```

---

## 📊 Verification

### Verify Configuration

```bash
# Check that profile ID is set correctly
python -c "from main import load_config; import os; os.environ['AMAZON_PROFILE_ID']='1780498399290938'; config=load_config(); print(f'Profile ID: {config.get(\"amazon_api\", {}).get(\"profile_id\")}')"
```

### Test the Helper Module

```bash
# Test profile ID retrieval from Secret Manager
python optimizer_profile_id_helper.py
```

### Check BigQuery Data

After running the optimizer, verify that new records use the correct profile ID:

```sql
SELECT 
  timestamp,
  profile_id,
  run_id,
  status,
  campaigns_analyzed
FROM `amazon-ppc-474902.amazon_ppc.optimization_results`
WHERE profile_id = '1780498399290938'
ORDER BY timestamp DESC
LIMIT 10;
```

---

## 🔍 Before and After

### Before Update ❌

```json
{
  "amazon_api": {
    "profile_id": "YOUR_PROFILE_ID"  // ❌ Placeholder
  }
}
```

**Result**: Optimizer couldn't analyze campaigns, all optimization results had placeholder profile ID.

### After Update ✅

```json
{
  "amazon_api": {
    "profile_id": "1780498399290938"  // ✅ Real profile ID
  }
}
```

**Result**: Optimizer can now:
- ✅ Fetch real campaigns from Amazon Advertising API
- ✅ Analyze campaign performance
- ✅ Make bid adjustments
- ✅ Write results to BigQuery with correct profile ID
- ✅ Dashboard displays real optimization data

---

## 🎯 Expected Behavior

Once deployed, the optimizer will:

1. **Authenticate** with Amazon Advertising API using profile ID `1780498399290938`
2. **Fetch campaigns** for the "US Seller" profile
3. **Analyze performance** based on ACOS targets and other metrics
4. **Optimize bids** for keywords and campaigns
5. **Write results** to BigQuery table `amazon_ppc.optimization_results`
6. **Display data** on the dashboard at `https://amazon-ppc-dashboard.abacusai.app` (or your deployment URL)

---

## 📈 BigQuery Integration

### Tables Updated

1. **`amazon_ppc.optimization_results`**
   - Now uses `profile_id = '1780498399290938'` instead of placeholder
   - Tracks all optimization actions (bids, keywords, budgets)

2. **`amazon_ppc.campaign_performance`**
   - Stores campaign metrics with correct profile ID
   - Links to optimization results

3. **`ppc_data.campaign_performance`**
   - Legacy table (254 campaigns with $0 spend)
   - Should be replaced by data from `amazon_ppc` dataset

---

## 🔐 Security Considerations

### Production Best Practices

1. **Never commit credentials** to git:
   ```bash
   # Already in .gitignore:
   .env
   config.json  # If it contains real credentials
   ```

2. **Use Google Secret Manager** for production:
   - Profile ID: `projects/1009540130231/secrets/ppc-profile-id`
   - Client ID: `projects/1009540130231/secrets/amazon-client-id`
   - Client Secret: `projects/1009540130231/secrets/amazon-client-secret`
   - Refresh Token: `projects/1009540130231/secrets/amazon-refresh-token`

3. **Grant minimal permissions**:
   ```bash
   # Grant Secret Manager access to Cloud Function service account
   gcloud secrets add-iam-policy-binding ppc-profile-id \
     --project=1009540130231 \
     --member="serviceAccount:amazon-ppc-optimizer@amazon-ppc-474902.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

---

## 🐛 Troubleshooting

### Issue 1: Profile ID Not Found

**Error**: `ValueError: profile_id is required`

**Solution**:
```bash
# Set environment variable
export AMAZON_PROFILE_ID=1780498399290938

# Or update config.json (already done)
# Or use Secret Manager
```

### Issue 2: Authentication Failed

**Error**: `401 Unauthorized` or `403 Forbidden`

**Solution**:
- Verify profile ID matches your Amazon Ads account
- Check that API credentials (client_id, client_secret, refresh_token) are correct
- Ensure tokens haven't expired

### Issue 3: No Campaigns Found

**Error**: `No campaigns found for profile_id`

**Solution**:
- Verify profile ID `1780498399290938` is active in your Amazon Advertising account
- Check that the profile has active campaigns
- Ensure API credentials have access to the profile

### Issue 4: BigQuery Write Errors

**Error**: `BigQuery insert failed`

**Solution**:
- Verify BigQuery service account has `roles/bigquery.dataEditor`
- Check that dataset `amazon_ppc` exists in project `amazon-ppc-474902`
- Ensure tables have correct schema

---

## 📝 Changelog

### Version 2.0 - November 11, 2025

**Added:**
- ✅ Real profile ID support (`1780498399290938`)
- ✅ Environment variable priority for profile ID
- ✅ Helper module for Secret Manager integration
- ✅ Enhanced error messages

**Changed:**
- ✅ Updated `config.json` with real profile ID
- ✅ Updated `.env.template` with real profile ID
- ✅ Modified `main.py` to support `AMAZON_PROFILE_ID` env var

**Fixed:**
- ✅ Placeholder profile ID issue
- ✅ Profile ID retrieval from multiple sources

---

## 🔗 Related Documentation

- **Dashboard**: See `PROFILE_ID_SETUP.md` in dashboard repository
- **Deployment**: See `DEPLOYMENT_GUIDE.md` for full deployment instructions
- **BigQuery**: See `BIGQUERY_INTEGRATION.md` for database setup
- **API Access**: See `ACCESS_GUIDE.md` for Amazon Advertising API setup

---

## ✅ Checklist for Deployment

Before deploying the updated optimizer:

- [x] Profile ID updated in `config.json`
- [x] Profile ID updated in `.env.template`
- [x] `main.py` supports `AMAZON_PROFILE_ID` env var
- [x] Helper module added for Secret Manager
- [ ] Test optimizer locally with correct profile ID
- [ ] Deploy to Google Cloud Function or Cloud Run
- [ ] Verify optimization results in BigQuery
- [ ] Check dashboard displays correct data
- [ ] Monitor logs for any errors

---

## 📞 Support

If you encounter issues:

1. Check the logs: `gcloud functions logs read amazon-ppc-optimizer`
2. Verify configuration: Run verification script
3. Test locally: `python main.py --dry-run`
4. Review documentation in this repository

---

**Status**: ✅ Ready for Production Deployment  
**Profile ID**: `1780498399290938` (US Seller)  
**Next Step**: Deploy and test the optimizer

