# Amazon PPC Dashboard - Next.js Application

This is the Next.js dashboard application that receives optimization data from the Amazon PPC Optimizer Cloud Function.

## Directory Structure

```
amazon_ppc_dashboard/nextjs_space/
├── app/
│   ├── api/
│   │   ├── health/route.ts                  - Health check endpoint
│   │   ├── config-check/route.ts            - Configuration diagnostics
│   │   ├── bigquery-data/route.ts           - BigQuery data queries
│   │   ├── optimization-status/route.ts     - Real-time progress updates
│   │   ├── optimization-results/route.ts    - Final optimization results
│   │   └── optimization-error/route.ts      - Error reporting
│   ├── layout.tsx                           - Root layout
│   └── page.tsx                             - Main dashboard page
├── .env.example                             - Environment variables template
├── .gitignore                               - Git ignore rules
├── next.config.js                           - Next.js configuration
├── package.json                             - Dependencies and scripts
├── tsconfig.json                            - TypeScript configuration
├── README.md                                - This file
├── README_BIGQUERY.md                       - BigQuery integration guide
└── DEPLOYMENT.md                            - Deployment instructions
```

## Getting Started

### Prerequisites

- Node.js 18.x or later
- npm or yarn

### Installation

1. Install dependencies:
```bash
npm install
```

2. Create a `.env.local` file from the example:
```bash
cp .env.example .env.local
```

3. Update the `.env.local` file with your actual values:
```
DASHBOARD_API_KEY=your_actual_api_key_here
```

### Development

Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

### Building for Production

Build the application:
```bash
npm run build
```

Start the production server:
```bash
npm start
```

## API Endpoints

### Health Check
**GET** `/api/health`

Returns the health status of the dashboard.

Response:
```json
{
  "status": "ok",
  "timestamp": "2025-10-18T...",
  "service": "Amazon PPC Dashboard"
}
```

### Configuration Check (NEW)
**GET** `/api/config-check`

Diagnoses configuration issues and shows what environment variables are set.

Response:
```json
{
  "status": "ok|warning|error",
  "message": "Configuration appears correct",
  "checks": {
    "configuration": {
      "gcp_project": {
        "set": true,
        "source": "GCP_PROJECT",
        "value": "amazon-ppc-474902"
      },
      "credentials": {
        "gcp_service_account_key": {
          "set": true,
          "valid_json": true,
          "has_required_fields": true
        }
      }
    },
    "diagnosis": [
      "✅ GCP project ID is configured",
      "✅ GCP_SERVICE_ACCOUNT_KEY is valid and contains required fields"
    ],
    "recommendations": []
  },
  "next_steps": [
    "Test BigQuery connection: GET /api/bigquery-data?table=optimization_results&limit=1"
  ]
}
```

**Use this endpoint to troubleshoot "GCP_PROJECT must be set" errors.**

### Optimization Status
**POST** `/api/optimization-status`

Receives real-time status updates during optimization runs.

Headers:
- `Authorization: Bearer YOUR_DASHBOARD_API_KEY`

Request Body:
```json
{
  "run_id": "unique-id",
  "status": "started|running|completed",
  "profile_id": "your-profile",
  "timestamp": "ISO timestamp",
  "message": "optional progress message",
  "percent_complete": 50
}
```

### Optimization Results
**POST** `/api/optimization-results`

Receives final optimization results.

Headers:
- `Authorization: Bearer YOUR_DASHBOARD_API_KEY`

Request Body:
```json
{
  "run_id": "unique-id",
  "status": "success",
  "profile_id": "your-profile",
  "timestamp": "ISO timestamp",
  "duration_seconds": 50.24,
  "dry_run": false,
  "summary": {
    "campaigns_analyzed": 253,
    "keywords_optimized": 1000,
    "bids_increased": 611
  }
}
```

### Optimization Error
**POST** `/api/optimization-error`

Receives error reports from failed optimization runs.

Headers:
- `Authorization: Bearer YOUR_DASHBOARD_API_KEY`

Request Body:
```json
{
  "run_id": "unique-id",
  "status": "error",
  "profile_id": "your-profile",
  "timestamp": "ISO timestamp",
  "error": "error message",
  "error_type": "error classification"
}
```

## Deployment to Vercel

### Option 1: Deploy from Vercel Dashboard

1. Go to [https://vercel.com/dashboard](https://vercel.com/dashboard)
2. Click "Add New Project"
3. Import from: `natureswaysoil/Amazom-PPC`
4. **Root Directory**: `amazon_ppc_dashboard/nextjs_space`
5. Click "Deploy"

### Option 2: Deploy with Vercel CLI

```bash
cd amazon_ppc_dashboard/nextjs_space
vercel
```

### Environment Variables in Vercel

Add these environment variables in Vercel Project Settings:

```
DASHBOARD_API_KEY=your_dashboard_api_key_here
NEXTAUTH_URL=https://amazonppcdashboard.vercel.app
```

## Testing

### Test Health Endpoint Locally
```bash
curl http://localhost:3000/api/health
```

### Test Health Endpoint (Production)
```bash
curl https://amazonppcdashboard.vercel.app/api/health
```

### Test from Cloud Function
```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://amazon-ppc-optimizer-nucguq3dba-uc.a.run.app?health=true"
```

Should show: `"dashboard_ok": true`

## Integration with Cloud Function

The Cloud Function optimizer automatically posts to these endpoints on every run:

1. **Start notification** → `/api/optimization-status`
2. **Progress updates** → `/api/optimization-status`
3. **Final results** → `/api/optimization-results`
4. **Errors** → `/api/optimization-error`

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

## License

This project is part of the Amazon PPC Optimizer system.

# Last updated: Fri Nov 14 18:55:20 UTC 2025
