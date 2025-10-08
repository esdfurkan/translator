import os
import sys
import time
import shutil
import requests
import configparser
from datetime import datetime
from PIL import Image
from dotenv import load_dotenv
import fitz
import zipfile
import rarfile
import py7zr
from ebooklib import epub

GECERLI_UZANTILAR = ('.png', '.jpg', '.jpeg', '.webp')
MAX_DOSYA_BOYUTU_MB = 15.0
HEDEF_BOYUT_MB = 14.8
API_URL = "https://api.toriitranslate.com/api/upload"

def perform_first_run_check(lang):
    if os.path.exists(".setup_complete"):
        return

    print(f"--- {lang.get('FIRST_RUN_HEADER', '--- First-Run Check ---')} ---")
    dependencies = {'7z': 'p7zip-full', 'unrar': 'unrar'}
    missing = {}

    for cmd in dependencies:
        if shutil.which(cmd):
            print(lang.get('FIRST_RUN_OK', '[OK] Command {dep} found.').format(dep=cmd))
        else:
            ext = ".cb7" if cmd == "7z" else ".cbr"
            print(lang.get('FIRST_RUN_WARN', '[WARNING] Command {dep} not found.').format(dep=cmd, ext=ext))
            missing[cmd] = dependencies[cmd]
    
    if missing:
        print(f"\n{lang.get('FIRST_RUN_INSTALL_SUGGESTION', '...')}")
        print(f"sudo apt install {' '.join(missing.values())}")

    print(f"{lang.get('FIRST_RUN_DONE', 'Setup check complete.')}")
    print("-" * 30)
    with open(".setup_complete", "w") as f:
        f.write("done")

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
        if 'error' in path_parts or any(part.endswith('_output') for part in path_parts):
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

def sorted_alphanumeric(data):
    import re
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(data, key=alphanum_key)

def extract_pdf(filepath, temp_dir):
    doc = fitz.open(filepath)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)
        pix.save(os.path.join(temp_dir, f"page_{i:04d}.png"))
    doc.close()

def extract_zip(filepath, temp_dir):
    with zipfile.ZipFile(filepath, 'r') as zf:
        image_files = [name for name in zf.namelist() if not name.startswith('__MACOSX') and name.lower().endswith(('.png', '.jpg', '.jpeg'))]
        for name in sorted_alphanumeric(image_files):
            zf.extract(name, temp_dir)

def extract_rar(filepath, temp_dir):
    with rarfile.RarFile(filepath, 'r') as rf:
        image_files = [name for name in rf.namelist() if name.lower().endswith(('.png', '.jpg', '.jpeg'))]
        for name in sorted_alphanumeric(image_files):
            rf.extract(name, temp_dir)
    
def extract_7z(filepath, temp_dir):
    with py7zr.SevenZipFile(filepath, mode='r') as z:
        z.extractall(path=temp_dir)

def extract_epub(filepath, temp_dir):
    book = epub.read_epub(filepath)
    image_map = {}
    i = 0
    for item in book.get_items_of_type(epub.ITEM_IMAGE):
        filename = item.get_name()
        ext = os.path.splitext(filename)[1]
        output_path = os.path.join(temp_dir, f"page_{i:04d}{ext}")
        with open(output_path, 'wb') as f:
            f.write(item.get_content())
        image_map[output_path] = filename
        i += 1
    return image_map

def repack_pdf(image_folder, output_path):
    images = []
    image_files = sorted_alphanumeric([os.path.join(image_folder, f) for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    for path in image_files:
        img = Image.open(path)
        if img.mode == 'RGBA': img = img.convert('RGB')
        images.append(img)
    if images:
        images[0].save(output_path, save_all=True, append_images=images[1:])

def repack_cbz(image_folder, output_path):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        image_files = sorted_alphanumeric([f for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        for filename in image_files:
            zf.write(os.path.join(image_folder, filename), arcname=filename)

def repack_epub(original_epub_path, translated_folder, image_map, output_path):
    book = epub.read_epub(original_epub_path)
    for local_path, epub_internal_name in image_map.items():
        base_name = os.path.splitext(os.path.basename(local_path))[0]
        translated_filename = f"{base_name}_translated.jpg"
        translated_path = os.path.join(translated_folder, translated_filename)
        
        if os.path.exists(translated_path):
            item = book.get_item_with_href(epub_internal_name)
            if item:
                with open(translated_path, 'rb') as f:
                    item.content = f.read()
                item.media_type = 'image/jpeg'
                new_filename = os.path.splitext(item.file_name)[0] + ".jpg"
                item.file_name = new_filename

    epub.write_epub(output_path, book, {})
