import requests
from bs4 import BeautifulSoup
import json
import os
import subprocess 
from tqdm import tqdm
import hashlib
import time
import requests
from requests.exceptions import RequestException

def get_uuid():
    url = "https://uupdump.net/fetchupd.php?arch=amd64&ring=canary"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        uuid_element = soup.find("code")
        return uuid_element.text.strip()
    except requests.RequestException as e:
        raise Exception(f"Error fetching UUID: {e}")



def verify_sha256(file_path, expected_hash):
    """Verify file's SHA256 hash matches expected value"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    actual_hash = sha256_hash.hexdigest()
    return actual_hash == expected_hash

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
            if response.status_code == 429:  # Too Many Requests
                if attempt < max_retries - 1:  # Don't sleep on last attempt
                    print(f"Rate limited. Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                    continue
            raise Exception(f"Error getting download URL: {e}")
            
        except KeyError as e:
            raise Exception(f"Error parsing response data: {e}")
    
    raise Exception("Max retries exceeded while getting download URL")

def download_esd(url, output_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Get total file size
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            with tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc="Downloading",
                ncols=80
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)
    except requests.RequestException as e:
        raise Exception(f"Error downloading ESD: {e}")

def convert_esd_to_wim(esd_path, output_dir):
    """Convert ESD to WIM format using DISM"""
    try:
        # Configure logging
        log_dir = os.path.join(output_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "dism_convert.log")
        
        # Generate WIM path
        wim_path = os.path.join(output_dir, "converted.wim")
        
        # Convert ESD to WIM with verbose logging
        convert_cmd = (
            f'dism /Export-Image /SourceImageFile:"{esd_path}" /SourceIndex:3 '
            f'/DestinationImageFile:"{wim_path}" /Compress:max '
            f'/Logpath:"{log_file}" /Loglevel:4'
        )
        subprocess.run(convert_cmd, check=True, shell=True)
        
        return wim_path
        
    except subprocess.CalledProcessError as e:
        # Read and include log file contents in error message
        log_content = ""
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f"\nDISM Log:\n" + f.read()
        raise Exception(f"DISM conversion failed: {e}{log_content}")

def extract_driver_policy(image_path, output_dir):
    """Extract driversipolicy.p7b from WIM using DISM with verbose logging"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        mount_path = os.path.join(output_dir, "mount")
        os.makedirs(mount_path, exist_ok=True)
        
        log_dir = os.path.join(output_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "dism.log")
        
        # Mount the WIM with verbose logging
        mount_cmd = (
            f'dism /Mount-Image /ImageFile:"{image_path}" /Index:1 /MountDir:"{mount_path}" '
            f'/Logpath:"{log_file}" /Loglevel:4'
        )
        subprocess.run(mount_cmd, check=True, shell=True)

        try:
            source = os.path.join(mount_path, "Windows", "System32", "CodeIntegrity", "driversipolicy.p7b")
            dest = os.path.join(output_dir, "driversipolicy.p7b")
            
            if os.path.exists(source):
                import shutil
                shutil.copy2(source, dest)
            else:
                raise Exception("driversipolicy.p7b not found in mounted image")

        finally:
            # Unmount with verbose logging
            unmount_cmd = (
                f'dism /Unmount-Image /MountDir:"{mount_path}" /Discard '
                f'/Logpath:"{log_file}" /Loglevel:4'
            )
            subprocess.run(unmount_cmd, check=True, shell=True)
            
            if os.path.exists(mount_path):
                os.rmdir(mount_path)

    except subprocess.CalledProcessError as e:
        log_content = ""
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f"\nDISM Log:\n" + f.read()
        raise Exception(f"DISM operation failed: {e}{log_content}")
    except Exception as e:
        raise Exception(f"Error extracting file: {e}")

def main():
    esd_path = None
    wim_path = None
    
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
        
        output_dir = "output"
        print("Converting ESD to WIM...")
        wim_path = convert_esd_to_wim(esd_path, output_dir)
        
        print("Extracting driversipolicy.p7b...")
        extract_driver_policy(wim_path, output_dir)
        
        print("Extraction complete!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up both ESD and WIM files
        if esd_path and os.path.exists(esd_path):
            os.remove(esd_path)
        if wim_path and os.path.exists(wim_path):
            os.remove(wim_path)

if __name__ == "__main__":
    main()