import json
import requests
import os
from datetime import datetime

def load_config():
    # Read from environment variables
    config = {}
    config['dashboard'] = {
        'url': os.getenv('DASHBOARD_URL', ''),
        'api_key': os.getenv('DASHBOARD_API_KEY', ''),
        'profile_id': os.getenv('DASHBOARD_PROFILE_ID', 'health-profile')
    }
    config['email'] = {
        'api_key': os.getenv('RESEND_API_KEY', ''),
        'from': os.getenv('RESEND_FROM', ''),
        'test_to': os.getenv('RESEND_TEST_TO', '')
    }
    return config

def check_dashboard(cfg):
    url = cfg['dashboard']['url']
    api_key = cfg['dashboard']['api_key']
    profile_id = cfg['dashboard']['profile_id']
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    headers['X-Profile-ID'] = str(profile_id)
    try:
        resp = requests.get(f"{url}/api/health", headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Dashboard health error: {e}")
        return False

def check_email(cfg):
    api_key = cfg['email']['api_key']
    from_addr = cfg['email']['from']
    to_addr = cfg['email']['test_to']
    if not (api_key and from_addr and to_addr):
        print("Email config missing api_key, from, or test_to address.")
        return False
    email_url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": from_addr,
        "to": to_addr,
        "subject": "Health Check Email from PPC Optimizer",
        "html": f"<strong>Health check at {datetime.now().isoformat()}</strong>"
    }
    try:
        resp = requests.post(email_url, json=payload, headers=headers, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Email send error: {e}")
        return False

def run_health_check(request):
    cfg = load_config()
    dashboard_ok = check_dashboard(cfg)
    email_ok = check_email(cfg)
    result = {
        "timestamp": datetime.now().isoformat(),
        "dashboard_ok": dashboard_ok,
        "email_ok": email_ok
    }
    print(json.dumps(result))
    status = 200 if dashboard_ok and email_ok else 500
    return (json.dumps(result), status, {"Content-Type": "application/json"})
