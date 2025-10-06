import os
import sys
import time
import shutil
import requests
from datetime import datetime
from PIL import Image

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

def find_all_images(folder):
    image_paths = []
    for root, _, files in os.walk(folder):
        path_parts = root.split(os.sep)
        if 'error' in path_parts or any(part.endswith('_output_') for part in path_parts):
            continue
        for file in files:
            if file.lower().endswith(GECERLI_UZANTILAR):
                image_paths.append(os.path.join(root, file))
    return image_paths

def copy_to_error_folder(file_path, source_folder, error_folder):
    if not os.path.exists(file_path):
        return
    
    relative_path = os.path.relpath(file_path, source_folder)
    error_target_path = os.path.join(error_folder, relative_path)
    error_target_dir = os.path.dirname(error_target_path)
    
    os.makedirs(error_target_dir, exist_ok=True)
    shutil.copy2(file_path, error_target_path)

def preprocess_image(file_path, source_folder, lang):
    if not os.path.exists(file_path) or os.path.getsize(file_path) <= MAX_DOSYA_BOYUTU_MB * 1024 * 1024:
        return True
        
    filename = os.path.basename(file_path)
    error_folder = os.path.join(source_folder, "error")
    target_size_bytes = HEDEF_BOYUT_MB * 1024 * 1024
    print(lang.get('INFO_COMPRESSING_IMAGE', '...').format(filename=filename, size_mb=os.path.getsize(file_path) / (1024*1024)), end='', flush=True)
    
    try:
        img = Image.open(file_path)
        if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
        
        temp_path = file_path + ".tmp.jpg"
        quality = 95
        img.save(temp_path, 'JPEG', quality=quality, optimize=True)

        if os.path.getsize(temp_path) > target_size_bytes:
            quality = 85
            while quality >= 75:
                img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                if os.path.getsize(temp_path) <= target_size_bytes: break
                quality -= 5
        
        if os.path.getsize(temp_path) > target_size_bytes:
            width, height = img.size
            while os.path.getsize(temp_path) > target_size_bytes:
                width, height = int(width * 0.95), int(height * 0.95)
                if width < 100 or height < 100: raise Exception("Image too small to compress.")
                img.resize((width, height), Image.Resampling.LANCZOS).save(temp_path, 'JPEG', quality=75, optimize=True)
        
        os.replace(temp_path, file_path)
        final_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(lang.get('INFO_COMPRESSION_DONE', '...').format(final_size_mb=final_size_mb))
        return True
    except Exception as e:
        print(lang.get('ERROR_COMPRESSION_GENERAL', '...').format(error=e))
        relative_path = os.path.relpath(file_path, source_folder)
        log_error(error_folder, relative_path, f"Sıkıştırma hatası: {e}")
        copy_to_error_folder(file_path, source_folder, error_folder)
        return False

def process_single_file(file_path, api_key, model, target_lang, source_folder, output_folder, error_folder, lang):
    filename = os.path.basename(file_path)
    relative_path = os.path.relpath(file_path, source_folder)
    try:
        with open(file_path, "rb") as image_file:
            headers = { "Authorization": f"Bearer {api_key}", "target_lang": target_lang, "translator": model, "font": "wildwords"}
            files = {"file": (filename, image_file, 'image/jpeg')}
            response = requests.post(API_URL, headers=headers, files=files, timeout=90)
            if response.headers.get("success") == "true":
                output_relative_dir = os.path.dirname(relative_path)
                output_subfolder = os.path.join(output_folder, output_relative_dir)
                os.makedirs(output_subfolder, exist_ok=True)
                output_path = os.path.join(output_subfolder, f"{os.path.splitext(filename)[0]}_translated.jpg")
                with open(output_path, "wb") as f_out: f_out.write(response.content)
                print(f"-> {lang.get('INFO_SUCCESS', 'SUCCESS!')}")
                return True
            else:
                error_msg = response.content.decode('utf-8', 'ignore')
                status_code = response.status_code
                log_message = f"API Hatası (Kod: {status_code}) - Mesaj: {error_msg}"
                print(f"-> {log_message}")
                log_error(error_folder, relative_path, log_message)
    except Exception as e:
        log_message = f"Genel Hata: {e}"
        print(f"-> {log_message}")
        log_error(error_folder, relative_path, log_message)

    copy_to_error_folder(file_path, source_folder, error_folder)
    return False
