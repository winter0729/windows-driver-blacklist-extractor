# check_update.py
import requests
import time
import os
from downloader import get_uuid

def get_update_info(uuid, max_retries=3, retry_delay=10):
    api_url = f'https://api.uupdump.net/get.php?id={uuid}&lang=en-us&edition=professional'
    
    for attempt in range(max_retries):
        try:
            response = requests.get(api_url)
            if response.status_code == 429:  # Rate limit
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
            response.raise_for_status()
            data = response.json()
            return data['response']['updateName']
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            raise e

def check_updates():
    current_uuid = get_uuid()
    update_name = get_update_info(current_uuid)
    
    # Write current UUID to file
    with open('current_uuid.txt', 'w') as f:
        f.write(current_uuid)
    
    # Check if update is needed
    update_needed = True
    if os.path.exists('latest.txt'):
        with open('latest.txt', 'r') as f:
            last_uuid = f.read().strip()
            update_needed = last_uuid != current_uuid
            
    return {
        'update_name': update_name,
        'update_needed': str(update_needed).lower()
    }

if __name__ == '__main__':
    result = check_updates()
    # GitHub Actions output format
    print(f"::set-output name=update_name::{result['update_name']}")
    print(f"::set-output name=update_needed::{result['update_needed']}")