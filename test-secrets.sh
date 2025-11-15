#!/bin/bash

echo "Testing Secret Manager values..."
echo "================================================"

PROJECT="amazon-ppc-474902"

echo ""
echo "AMAZON_CLIENT_ID length:"
gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="$PROJECT" | wc -c

echo ""
echo "AMAZON_CLIENT_ID (first 20 chars):"
gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="$PROJECT" | head -c 20
echo ""

echo ""
echo "AMAZON_CLIENT_ID (last 20 chars):"
gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="$PROJECT" | tail -c 20
echo ""

echo ""
echo "AMAZON_CLIENT_SECRET length:"
gcloud secrets versions access latest --secret="AMAZON_CLIENT_SECRET" --project="$PROJECT" | wc -c

echo ""
echo "AMAZON_REFRESH_TOKEN length:"
gcloud secrets versions access latest --secret="AMAZON_REFRESH_TOKEN" --project="$PROJECT" | wc -c

echo ""
echo "AMAZON_REFRESH_TOKEN (first 30 chars):"
gcloud secrets versions access latest --secret="AMAZON_REFRESH_TOKEN" --project="$PROJECT" | head -c 30
echo ""

echo ""
echo "AMAZON_REFRESH_TOKEN (last 30 chars):"
gcloud secrets versions access latest --secret="AMAZON_REFRESH_TOKEN" --project="$PROJECT" | tail -c 30
echo ""

echo ""
echo "Checking for hidden characters..."
gcloud secrets versions access latest --secret="AMAZON_CLIENT_ID" --project="$PROJECT" | od -c | head -5

echo ""
echo "Done!"
