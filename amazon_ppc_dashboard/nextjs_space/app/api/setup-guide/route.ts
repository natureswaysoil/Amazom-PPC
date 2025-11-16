import { NextRequest, NextResponse } from 'next/server';
import { resolveGCPCredentials, getFirstSetEnv, PROJECT_ID_ENV_NAMES } from '../lib/credentials';

/**
 * Interactive setup guide endpoint
 * Provides step-by-step instructions to get the dashboard working
 */
export async function GET(request: NextRequest) {
  const setupSteps = [];
  let currentStep = 1;
  let allStepsComplete = true;
  
  // Step 1: Check GCP Credentials
  const credentialResult = resolveGCPCredentials();
  const step1 = {
    step: currentStep++,
    title: 'Google Cloud Service Account Credentials',
    status: credentialResult.success ? 'complete' : 'incomplete',
    required: true,
    description: 'Service account credentials are required to read optimization data from BigQuery',
    currentValue: credentialResult.success 
      ? `✓ Credentials loaded from ${credentialResult.source}` 
      : '✗ No valid credentials found',
    instructions: credentialResult.success ? [] : [
      'Download your service account key JSON file from Google Cloud Console',
      'Go to: https://console.cloud.google.com/iam-admin/serviceaccounts',
      'Select your service account (or create a new one)',
      'Go to "Keys" tab → "Add Key" → "Create new key" → JSON format',
      'Copy the entire JSON file contents',
      'In your Vercel/deployment platform, set environment variable: GCP_SERVICE_ACCOUNT_KEY',
      'Paste the JSON as the value (can be raw JSON or base64-encoded)',
      'Redeploy the dashboard',
    ],
    helpfulLinks: [
      'https://cloud.google.com/iam/docs/keys-create-delete',
      'https://vercel.com/docs/projects/environment-variables',
    ],
  };
  setupSteps.push(step1);
  if (step1.status === 'incomplete') allStepsComplete = false;
  
  // Step 2: Check Project ID
  const projectId = getFirstSetEnv(PROJECT_ID_ENV_NAMES);
  const step2 = {
    step: currentStep++,
    title: 'Google Cloud Project ID',
    status: projectId ? 'complete' : 'warning',
    required: false,
    description: 'Project ID helps identify which GCP project to use',
    currentValue: projectId 
      ? `✓ Using project: ${projectId}` 
      : 'Using default project (amazon-ppc-474902)',
    instructions: projectId ? [] : [
      'Optional: Set GCP_PROJECT or GOOGLE_CLOUD_PROJECT environment variable',
      'Use your actual Google Cloud project ID',
      'If not set, the default project will be used',
    ],
  };
  setupSteps.push(step2);
  
  // Step 3: Service Account Permissions
  const step3 = {
    step: currentStep++,
    title: 'BigQuery Permissions',
    status: credentialResult.success ? 'needs_verification' : 'incomplete',
    required: true,
    description: 'Service account needs permissions to read BigQuery data',
    currentValue: credentialResult.success 
      ? 'Credentials loaded - permissions need verification' 
      : 'Cannot check until credentials are configured',
    instructions: credentialResult.success ? [
      'Test BigQuery access by visiting: /api/bigquery-data?limit=1',
      'If you see a permissions error, grant these roles to your service account:',
      '  • roles/bigquery.dataViewer (to read data)',
      '  • roles/bigquery.jobUser (to run queries)',
      '',
      'To grant permissions in Google Cloud Console:',
      '1. Go to: https://console.cloud.google.com/iam-admin/iam',
      '2. Find your service account in the list',
      '3. Click "Edit" (pencil icon)',
      '4. Add the required roles',
      '5. Click "Save"',
      '',
      'Or use gcloud CLI:',
      `gcloud projects add-iam-policy-binding ${projectId || 'YOUR_PROJECT_ID'} \\`,
      `  --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \\`,
      `  --role="roles/bigquery.dataViewer"`,
      `gcloud projects add-iam-policy-binding ${projectId || 'YOUR_PROJECT_ID'} \\`,
      `  --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \\`,
      `  --role="roles/bigquery.jobUser"`,
    ] : [
      'Configure credentials first (Step 1)',
    ],
  };
  setupSteps.push(step3);
  if (step3.status === 'incomplete') allStepsComplete = false;
  
  // Step 4: BigQuery Dataset
  const step4 = {
    step: currentStep++,
    title: 'BigQuery Dataset and Tables',
    status: 'needs_verification',
    required: true,
    description: 'The optimizer must have created the BigQuery dataset and tables',
    currentValue: 'Dataset existence needs verification',
    instructions: [
      'The optimizer automatically creates the BigQuery dataset and tables when it runs',
      'If tables don\'t exist, run the optimizer at least once',
      'The optimizer creates these tables:',
      '  • optimization_results - Main results data',
      '  • campaign_details - Campaign-level breakdown',
      '  • optimizer_run_events - Run history',
      '',
      'Verify by visiting: /api/bigquery-data?limit=1',
      'If you see a "Not found" error, trigger an optimization run',
    ],
  };
  setupSteps.push(step4);
  
  // Step 5: Test the Dashboard
  const step5 = {
    step: currentStep++,
    title: 'Test Dashboard Data',
    status: allStepsComplete ? 'ready' : 'waiting',
    required: true,
    description: 'Verify that live data is displayed on the dashboard',
    currentValue: allStepsComplete ? 'Ready to test' : 'Complete previous steps first',
    instructions: allStepsComplete ? [
      'Go to the dashboard home page: /',
      'You should see optimization results and statistics',
      'If you see errors, check the previous steps',
      'If you see "No optimization runs found", trigger an optimization',
    ] : [
      'Complete steps 1-4 first',
    ],
  };
  setupSteps.push(step5);
  
  // Overall status
  const overallStatus = {
    complete: allStepsComplete,
    totalSteps: setupSteps.length,
    completedSteps: setupSteps.filter(s => s.status === 'complete').length,
    message: allStepsComplete 
      ? '✓ Basic setup is complete! Test the dashboard at /' 
      : 'Setup incomplete - follow the steps below',
  };
  
  return NextResponse.json({
    success: true,
    timestamp: new Date().toISOString(),
    status: overallStatus,
    setupSteps,
    quickStart: {
      title: 'Quick Start (2 minutes)',
      steps: [
        '1. Get service account key from Google Cloud Console',
        '2. Set GCP_SERVICE_ACCOUNT_KEY in Vercel environment variables',
        '3. Grant BigQuery permissions (dataViewer + jobUser roles)',
        '4. Redeploy and visit /',
      ],
    },
    troubleshooting: {
      noDataShowing: [
        'Check /api/config-check for configuration issues',
        'Check /api/bigquery-data?limit=1 to test BigQuery connection',
        'Ensure the optimizer has run at least once to populate data',
        'Check service account has BigQuery permissions',
      ],
      credentialErrors: [
        'Verify GCP_SERVICE_ACCOUNT_KEY contains valid JSON',
        'Try base64 encoding: cat service-account.json | base64 | tr -d "\\n"',
        'Ensure no extra spaces or newlines in the environment variable',
        'Redeploy after changing environment variables',
      ],
      permissionErrors: [
        'Grant roles/bigquery.dataViewer to service account',
        'Grant roles/bigquery.jobUser to service account',
        'Wait 1-2 minutes for permission changes to propagate',
        'Verify you\'re using the correct project ID',
      ],
    },
  }, { 
    status: 200,
    headers: {
      'Cache-Control': 'no-cache, no-store, must-revalidate',
    }
  });
}
