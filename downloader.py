import requests
from bs4 import BeautifulSoup
import hashlib
import time
import os
from tqdm import tqdm
from requests.exceptions import RequestException

import time
from requests.exceptions import RequestException

def get_uuid():
    url = "https://uupdump.net/fetchupd.php?arch=amd64&ring=canary"
    max_attempts = 6
    attempt = 1
    
    while attempt <= max_attempts:
        try:
            response = requests.get(url)
            if response.status_code == 429:
                if attempt == max_attempts:
                    raise Exception("Max retry attempts reached after receiving 429 status")
                sleep_time = 10
                print(f"Rate limited (429). Retrying in {sleep_time} seconds... (Attempt {attempt}/{max_attempts})")
                time.sleep(sleep_time)
                attempt += 1
                continue
                
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            uuid_element = soup.find("code")
            return uuid_element.text.strip()
            
        except RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 429:
                continue
            raise Exception(f"Error fetching UUID: {e}")
        
def verify_sha256(file_path, expected_hash):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest() == expected_hash

def get_download_url(uuid, max_retries=6, initial_delay=10):
    api_url = f"https://api.uupdump.net/get.php?id={uuid}&lang=en-us&edition=professional"
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            file_info = data['response']['files']['MetadataESD_professional_en-us.esd']
            return file_info['url'], file_info['sha256']
        except RequestException as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                print(f"Rate limited. Waiting {delay} seconds...")
                time.sleep(delay)
                delay *= 2
                continue
            raise Exception(f"Error getting download URL: {e}")
    raise Exception("Max retries exceeded")

def download_esd(url, output_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)
    except requests.RequestException as e:
        raise Exception(f"Error downloading ESD: {e}")

def main():
    try:
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        
        uuid = get_uuid()
        download_url, expected_hash = get_download_url(uuid)
        
        esd_path = os.path.join(temp_dir, "metadata.esd")
        download_esd(download_url, esd_path)
        
        print("Verifying file integrity...")
        if not verify_sha256(esd_path, expected_hash):
            raise Exception("SHA256 verification failed - file may be corrupted")
        print("File integrity verified!")
        print(f"ESD file downloaded successfully to: {esd_path}")
        
    except Exception as e:
        print(f"Error: {e}")
        if os.path.exists(esd_path):
            os.remove(esd_path)

if __name__ == "__main__":
    main()