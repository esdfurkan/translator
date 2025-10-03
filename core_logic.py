import os
import sys
import time
import requests
import configparser
from datetime import datetime
from PIL import Image
from dotenv import load_dotenv

config = configparser.ConfigParser()
config.read('config.ini')
NEXTCLOUD_ENABLED = config.getboolean('Features', 'nextcloud_enabled', fallback=False)

NEXTCLOUD_STRATEGY = None
NextCloud = None
WebdavClient = None

if NEXTCLOUD_ENABLED:
    try:
        from nextcloud_api_wrapper import NextCloud
        NEXTCLOUD_STRATEGY = 'api_wrapper'
    except ImportError:
        try:
            from webdav.client import Client as WebdavClient
            NEXTCLOUD_STRATEGY = 'webdav'
        except ImportError:
            NEXTCLOUD_STRATEGY = None

GECERLI_UZANTILAR = ('.png', '.jpg', '.jpeg', '.webp')
MAX_DOSYA_BOYUTU_MB = 15.0
HEDEF_BOYUT_MB = 14.8
API_URL = "https://api.toriitranslate.com/api/upload"

def log_error(error_folder, filename, message):
    os.makedirs(error_folder, exist_ok=True)
    log_file_path = os.path.join(error_folder, "log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] - {filename} - {message}\n")

def preprocess_and_compress_images(folder_path, lang):
    print(f"\n--- {lang.get('HEADER_PREPROCESS', '--- Image Pre-processing and Compression ---')} ---")
    target_size_bytes = HEDEF_BOYUT_MB * 1024 * 1024
    files_to_check = [f for f in os.listdir(folder_path) if f.lower().endswith(GECERLI_UZANTILAR)]
    if not files_to_check:
        print(lang.get('INFO_NO_IMAGES_TO_PROCESS', 'No images found to process.'))
        return

    print(lang.get('INFO_CHECKING_IMAGE_SIZES', "Checking image sizes in '{folder}' folder...").format(folder=folder_path))
    for filename in files_to_check:
        file_path = os.path.join(folder_path, filename)
        if os.path.exists(file_path) and os.path.getsize(file_path) > MAX_DOSYA_BOYUTU_MB * 1024 * 1024:
            print(lang.get('INFO_COMPRESSING_IMAGE', '-> Compressing: {filename} ({size_mb:.2f} MB)...').format(filename=filename, size_mb=os.path.getsize(file_path) / (1024*1024)), end='', flush=True)
            try:
                img = Image.open(file_path)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                temp_path = file_path + ".tmp.jpg"
                quality = 95
                
                img.save(temp_path, 'JPEG', quality=quality, optimize=True)

                if os.path.getsize(temp_path) > target_size_bytes:
                    quality = 85
                    while quality >= 75:
                        img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                        if os.path.getsize(temp_path) <= target_size_bytes:
                            break
                        quality -= 5
                
                if os.path.getsize(temp_path) > target_size_bytes:
                    width, height = img.size
                    while os.path.getsize(temp_path) > target_size_bytes:
                        width = int(width * 0.95)
                        height = int(height * 0.95)
                        if width < 100 or height < 100:
                            raise Exception("Image dimensions too small to compress further.")
                        img.resize((width, height), Image.Resampling.LANCZOS).save(temp_path, 'JPEG', quality=75, optimize=True)
                
                os.replace(temp_path, file_path)
                final_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(lang.get('INFO_COMPRESSION_DONE', ' Done. New size: {final_size_mb:.2f} MB').format(final_size_mb=final_size_mb))
            except Exception as e:
                print(lang.get('ERROR_COMPRESSION_GENERAL', '-> An error occurred during compression: {error}').format(error=e))
                error_folder = os.path.join(os.path.dirname(file_path), "error")
                log_error(error_folder, filename, f"Sıkıştırma hatası: {e}")
                if os.path.exists(file_path):
                    os.rename(file_path, os.path.join(error_folder, filename))

def process_images(api_key, model_name, source_folder, lang, target_language):
    print(f"\n--- {lang.get('HEADER_TRANSLATION_START', '--- Starting Translation Process ---')} ---")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_folder = f"{source_folder}_output_{timestamp}"
    error_folder = os.path.join(source_folder, "error")
    os.makedirs(output_folder, exist_ok=True)

    image_files = [f for f in os.listdir(source_folder) if f.lower().endswith(GECERLI_UZANTILAR)]
    total_images = len(image_files)
    if total_images == 0:
        return output_folder, False
    
    any_errors = False
    for i, filename in enumerate(image_files):
        file_path = os.path.join(source_folder, filename)
        if not os.path.exists(file_path): continue
        
        print(lang.get('INFO_PROCESSING', '[{i}/{total}] Processing: {filename}').format(i=i+1, total=total_images, filename=filename))
        
        try:
            with open(file_path, "rb") as image_file:
                headers = { "Authorization": f"Bearer {api_key}", "target_lang": target_language, "translator": model_name, "font": "wildwords"}
                files = {"file": (filename, image_file, 'image/jpeg')}
                response = requests.post(API_URL, headers=headers, files=files, timeout=90)
                if response.headers.get("success") == "true":
                    output_path = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}_translated.jpg")
                    with open(output_path, "wb") as f_out:
                        f_out.write(response.content)
                    print(f"-> {lang.get('INFO_SUCCESS', 'SUCCESS!')}")
                else:
                    any_errors = True
                    error_msg = response.content.decode('utf-8', 'ignore')
                    status_code = response.status_code
                    log_message = f"API Hatası (Kod: {status_code}) - Mesaj: {error_msg}"
                    print(f"-> {log_message}")
                    log_error(error_folder, filename, log_message)
                    if os.path.exists(file_path): os.rename(file_path, os.path.join(error_folder, filename))
        except Exception as e:
            any_errors = True
            log_message = f"Genel Hata: {e}"
            print(f"-> {log_message}")
            log_error(error_folder, filename, log_message)
            if os.path.exists(file_path): os.rename(file_path, os.path.join(error_folder, filename))
        time.sleep(0.1)
    print(f"\n--- {lang.get('HEADER_TRANSLATION_DONE', '--- Translation Process Complete! ---')} ---")
    return output_folder, not any_errors

def upload_to_nextcloud(path_to_upload, lang):
    if not NEXTCLOUD_ENABLED:
        return None

    if not os.path.exists("nextcloud.env"):
        print(f"\n{lang.get('ERROR_NEXTCLOUD_CONFIG_MISSING', 'WARNING: ...')}")
        return None
    
    if not NEXTCLOUD_STRATEGY:
        print(f"\n{lang.get('ERROR_NO_NEXTCLOUD_LIBRARY', 'ERROR: ...')}")
        return None

    print(f"\n--- {lang.get('HEADER_NEXTCLOUD_UPLOAD', '--- Nextcloud Upload ---')} ---")
    try:
        load_dotenv(dotenv_path="nextcloud.env")
        nc_url, nc_user, nc_pass = os.getenv("NEXTCLOUD_URL"), os.getenv("NEXTCLOUD_USER"), os.getenv("NEXTCLOUD_APP_PASSWORD")
        if not all([nc_url, nc_user, nc_pass]):
            print("HATA: nextcloud.env dosyasındaki bilgiler eksik.")
            return None
        print(lang.get('INFO_UPLOADING_TO_NEXTCLOUD', 'Uploading to Nextcloud, please wait...'))
        
        base_remote_folder = lang.get('NEXTCLOUD_REMOTE_FOLDER_NAME', 'Translated')
        local_name = os.path.basename(path_to_upload)

        if NEXTCLOUD_STRATEGY == 'api_wrapper':
            nc = NextCloud(nc_url, nc_user, nc_pass)
            nc.mkdir(base_remote_folder)
            remote_path = f"{base_remote_folder}/{local_name}"
            if os.path.isdir(path_to_upload):
                nc.upload_dir(path_to_upload, remote_path)
            else:
                nc.upload_file(path_to_upload, remote_path)
            
            share_info = nc.create_share(remote_path)
            print(f"\n{lang.get('INFO_UPLOAD_SUCCESS', 'Upload successful!')}")
            if share_info and 'url' in share_info:
                link = share_info['url']
                print(lang.get('INFO_SHARE_LINK', 'Share Link: {link}').format(link=link))
                return link
        
        elif NEXTCLOUD_STRATEGY == 'webdav':
            options = { 'webdav_hostname': nc_url, 'webdav_login': nc_user, 'webdav_password': nc_pass }
            client = WebdavClient(options)
            remote_base_path = f"/remote.php/dav/files/{nc_user}/"
            client.mkdir(remote_base_path + base_remote_folder)
            remote_path_full = remote_base_path + f"{base_remote_folder}/{local_name}"

            if os.path.isdir(path_to_upload):
                client.upload_sync(remote_path=remote_path_full, local_path=path_to_upload)
            else:
                client.upload_sync(remote_path=remote_path_full, local_path=path_to_upload)
            
            print(f"\n{lang.get('INFO_UPLOAD_SUCCESS_NO_LINK', 'Upload successful, but could not create share link.')}")
            return None

    except Exception as e:
        if "Login failed" in str(e) or "Unauthorized" in str(e):
            print(f"\n{lang.get('ERROR_NEXTCLOUD_LOGIN', 'ERROR: Could not connect to Nextcloud.')}")
        else:
            print(f"\n{lang.get('ERROR_NEXTCLOUD_UPLOAD', 'ERROR: An issue occurred during upload: {error}').format(error=e)}")
    return None

def send_notification(lang, success, folder_name, nextcloud_link=None):
    webhook_config_path = "webhook.env"
    if not os.path.exists(webhook_config_path):
        return
    config = configparser.ConfigParser()
    config.read(webhook_config_path, encoding='utf-8')
    if not config.sections():
        return

    print(f"\n{lang.get('HEADER_WEBHOOK', '--- Sending Notification ---')}")
    if success:
        message = lang.get('WEBHOOK_MESSAGE_SUCCESS', '...').format(folder_name=folder_name, link=nextcloud_link or "N/A")
    else:
        message = lang.get('WEBHOOK_MESSAGE_FAILURE', '...').format(folder_name=folder_name)

    for section in config.sections():
        try:
            service_type = config.get(section, 'type', fallback='').lower()
            if not service_type: continue
            payload, url = {}, ""
            
            if service_type == 'discord':
                url = config.get(section, 'url', fallback='')
                payload = {"content": message}
            elif service_type == 'slack' or service_type == 'teams':
                url = config.get(section, 'url', fallback='')
                payload = {"text": message}
            elif service_type == 'telegram':
                token = config.get(section, 'token', fallback='')
                chat_id = config.get(section, 'chat_id', fallback='')
                if not token or not chat_id: continue
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            elif service_type == 'ifttt':
                url = config.get(section, 'url', fallback='')
                payload = {"value1": folder_name, "value2": nextcloud_link or "N/A", "value3": "Basarili" if success else "Hata"}
            elif service_type == 'generic':
                url = config.get(section, 'url', fallback='')
                payload = {"message": message, "folder": folder_name, "link": nextcloud_link, "success": success}

            if url:
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                print(lang.get('INFO_WEBHOOK_SUCCESS', '...').format(service=section))
        except Exception as e:
            print(lang.get('INFO_WEBHOOK_FAILED', '...').format(service=section, error=e))
