#!/usr/bin/env python3
"""
Google Sheets CSV Fetcher with Robust Error Handling
This utility helps prevent Cloud Run Job timeouts when accessing Google Sheets.

Usage:
    from google_sheet_fetcher import fetch_google_sheet_csv
    
    csv_data = fetch_google_sheet_csv()
    if csv_data is None:
        sys.exit(1)  # Fast fail instead of timeout
    
    # Process CSV data
    for row in csv.DictReader(csv_data.splitlines()):
        print(row)
"""

import os
import sys
import time
import csv
from typing import Optional, Dict, List
from io import StringIO

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


class GoogleSheetFetcher:
    """Robust Google Sheet CSV fetcher with error handling and retries"""
    
    def __init__(
        self,
        csv_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        retry_delay: int = 2
    ):
        """
        Initialize the fetcher.
        
        Args:
            csv_url: Google Sheet CSV export URL (defaults to CSV_URL env var)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            retry_delay: Base delay between retries (exponential backoff)
        """
        self.csv_url = csv_url or os.getenv('CSV_URL')
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_delay = retry_delay
        
        if not self.csv_url:
            raise ValueError("CSV_URL must be provided or set as environment variable")
    
    def validate_url_format(self) -> bool:
        """
        Validate that the URL is in correct CSV export format.
        
        Returns:
            True if format appears correct, False otherwise
        """
        if not self.csv_url:
            return False
        
        # Check for CSV export format
        if '/export?format=csv' in self.csv_url:
            return True
        
        # Warn about common incorrect formats
        if '/edit' in self.csv_url or 'docs.google.com/spreadsheets' in self.csv_url:
            print("WARNING: CSV_URL may not be in CSV export format", file=sys.stderr)
            print(f"Current: {self.csv_url}", file=sys.stderr)
            print("Expected: https://docs.google.com/spreadsheets/d/{ID}/export?format=csv&gid=0", file=sys.stderr)
            return False
        
        return False
    
    def fetch(self) -> Optional[str]:
        """
        Fetch CSV data from Google Sheet with retries.
        
        Returns:
            CSV content as string, or None if failed
        """
        # Validate URL format first
        if not self.validate_url_format():
            print("WARNING: Proceeding with potentially incorrect URL format", file=sys.stderr)
        
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"Attempting to fetch Google Sheet (attempt {attempt}/{self.max_retries})...")
                
                response = requests.get(
                    self.csv_url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    headers={
                        'User-Agent': 'Cloud-Run-Job/1.0',
                        'Accept': 'text/csv,text/plain'
                    }
                )
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                
                # If we got HTML, it's an error page
                if 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE html>'):
                    self._handle_html_response(response, attempt)
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay ** attempt)
                        continue
                    return None
                
                # Check HTTP status
                if response.status_code == 200:
                    print(f"✓ Successfully fetched CSV data ({len(response.text)} bytes)")
                    return response.text
                elif response.status_code == 403:
                    print(f"ERROR: HTTP 403 - Permission denied", file=sys.stderr)
                    print("The sheet may be private. Check permissions.", file=sys.stderr)
                    return None  # Don't retry permission errors
                elif response.status_code == 404:
                    print(f"ERROR: HTTP 404 - Sheet not found", file=sys.stderr)
                    print(f"URL: {self.csv_url}", file=sys.stderr)
                    return None  # Don't retry 404s
                else:
                    print(f"ERROR: HTTP {response.status_code}: {response.reason}", file=sys.stderr)
                
            except requests.Timeout:
                print(f"ERROR: Request timeout after {self.timeout}s", file=sys.stderr)
            except requests.RequestException as e:
                print(f"ERROR: Request failed: {e}", file=sys.stderr)
            except Exception as e:
                print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
            
            # Exponential backoff for retries
            if attempt < self.max_retries:
                wait_time = self.retry_delay ** attempt
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        print("FATAL: All retry attempts exhausted", file=sys.stderr)
        return None
    
    def _handle_html_response(self, response: requests.Response, attempt: int):
        """Handle HTML error page responses"""
        print(f"ERROR: Received HTML instead of CSV (Status: {response.status_code})", file=sys.stderr)
        print(f"URL: {self.csv_url}", file=sys.stderr)
        
        # Try to extract useful error info from HTML
        text_preview = response.text[:1000]
        
        if 'Page Not Found' in text_preview or '404' in text_preview:
            print("Error type: Page Not Found (404)", file=sys.stderr)
        elif 'Access Denied' in text_preview or 'Forbidden' in text_preview:
            print("Error type: Access Denied (403)", file=sys.stderr)
        
        print(f"Response preview: {response.text[:500]}", file=sys.stderr)
    
    def fetch_as_dict_list(self) -> Optional[List[Dict]]:
        """
        Fetch and parse CSV as list of dictionaries.
        
        Returns:
            List of dicts (one per row), or None if failed
        """
        csv_text = self.fetch()
        if csv_text is None:
            return None
        
        try:
            reader = csv.DictReader(StringIO(csv_text))
            return list(reader)
        except csv.Error as e:
            print(f"ERROR: Failed to parse CSV: {e}", file=sys.stderr)
            return None


def fetch_google_sheet_csv(
    csv_url: Optional[str] = None,
    max_retries: int = 3,
    timeout: int = 30
) -> Optional[str]:
    """
    Convenience function to fetch Google Sheet CSV.
    
    Args:
        csv_url: Google Sheet CSV export URL (defaults to CSV_URL env var)
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        CSV content as string, or None if failed
    
    Example:
        csv_data = fetch_google_sheet_csv()
        if csv_data is None:
            sys.exit(1)
        
        for row in csv.DictReader(csv_data.splitlines()):
            print(row)
    """
    fetcher = GoogleSheetFetcher(csv_url, max_retries, timeout)
    return fetcher.fetch()


def fetch_google_sheet_as_dict_list(
    csv_url: Optional[str] = None,
    max_retries: int = 3,
    timeout: int = 30
) -> Optional[List[Dict]]:
    """
    Convenience function to fetch and parse Google Sheet as list of dicts.
    
    Args:
        csv_url: Google Sheet CSV export URL (defaults to CSV_URL env var)
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        List of dicts (one per row), or None if failed
    
    Example:
        rows = fetch_google_sheet_as_dict_list()
        if rows is None:
            sys.exit(1)
        
        for row in rows:
            print(f"Name: {row['name']}, Value: {row['value']}")
    """
    fetcher = GoogleSheetFetcher(csv_url, max_retries, timeout)
    return fetcher.fetch_as_dict_list()


def main():
    """CLI tool to test Google Sheet access"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test Google Sheet CSV access with robust error handling'
    )
    parser.add_argument(
        '--url',
        help='Google Sheet CSV URL (defaults to CSV_URL env var)'
    )
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Maximum retry attempts (default: 3)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    parser.add_argument(
        '--preview',
        type=int,
        default=5,
        help='Number of rows to preview (default: 5)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Google Sheet CSV Fetcher - Test Utility")
    print("=" * 60)
    print()
    
    # Fetch CSV
    fetcher = GoogleSheetFetcher(
        csv_url=args.url,
        max_retries=args.max_retries,
        timeout=args.timeout
    )
    
    csv_data = fetcher.fetch()
    
    if csv_data is None:
        print()
        print("FAILED: Could not fetch Google Sheet")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("SUCCESS: CSV Data Retrieved")
    print("=" * 60)
    print()
    print(f"Total size: {len(csv_data)} bytes")
    print(f"Total lines: {len(csv_data.splitlines())}")
    print()
    print(f"Preview (first {args.preview} lines):")
    print("-" * 60)
    for i, line in enumerate(csv_data.splitlines()[:args.preview], 1):
        print(f"{i:3d} | {line}")
    print("-" * 60)
    print()
    print("✓ Google Sheet access is working correctly!")


if __name__ == '__main__':
    main()
