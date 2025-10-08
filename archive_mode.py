import os
import sys
import getpass
import time
import json
from dotenv import load_dotenv
import core_logic
import configparser
import tempfile

def save_profile(profile_data):
    with open('profile.json', 'w', encoding='utf-8') as f:
        json.dump(profile_data, f, indent=4)

def find_all_archives(root_folder, lang):
    print(lang.get('INFO_SCANNING_ARCHIVES', '...'), end='', flush=True)
    archive_paths = []
    supported_exts = ('.pdf', '.cbz', '.cbr', '.cb7', '.epub', '.zip', '.rar', '.7z')
    for root, dirs, files in os.walk(root_folder):
        dirs[:] = [d for d in dirs if not d.startswith('.') and 'lang' not in d and '_output' not in d and 'error' not in d]
        for file in files:
            if file.lower().endswith(supported_exts):
                archive_paths.append(os.path.join(root, file))
    print(" Tamamlandı.")
    return archive_paths

def start_archive_cli(lang, profile):
    core_logic.perform_first_run_check(lang)
    print("--- Arşiv Dosyası Çevirme Aracı ---")

    profile_exists = 'model_name' in profile

    api_key = ""
    api_env_path = "api.env"
    load_dotenv(dotenv_path=api_env_path)
    saved_api_key = os.getenv("API_KEY")

    if saved_api_key:
        print(lang.get('INFO_API_KEY_FOUND', '...'))
        api_key = saved_api_key
    else:
        print(f"\n{lang.get('INFO_GET_API_KEY', '...')}")
        print(f"{lang.get('INFO_EXAMPLE_KEY', '...')}")
        api_key = getpass.getpass(lang.get('PROMPT_API_KEY', '...') + " ")
        if not api_key.strip():
            print(lang.get('ERROR_API_KEY_EMPTY', '...')); return
        while True:
            save_confirm = input(f"\n{lang.get('PROMPT_SAVE_API_KEY', '...')} ").lower()
            if save_confirm in ['e', 'evet', 'y', 'yes']:
                with open(api_env_path, "w", encoding='utf-8') as f: f.write(f"API_KEY={api_key}\n")
                print(lang.get('INFO_API_KEY_SAVED', '...')); break
            elif save_confirm in ['h', 'hayır', 'n', 'no']: break
    
    if profile_exists:
        print(f"\n{lang.get('INFO_PROFILE_LOADED', '...')}")
        lang_code = os.path.splitext(os.path.basename(profile['language_file']))[0]
        target_language = profile['target_language']
        selected_model = profile['model_name']
        print(lang.get('INFO_PROFILE_LANG', '...').format(lang=lang_code))
        print(lang.get('INFO_PROFILE_TARGET', '...').format(target=target_language))
        print(lang.get('INFO_PROFILE_MODEL', '...').format(model=selected_model))
        
        models_path = "models.env"
        if not os.path.exists(models_path): print(f"HATA: '{models_path}' dosyası bulunamadı."); return
        models = {}
        with open(models_path, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith("#"): key, value = line.strip().split('=', 1); models[key] = value
        selected_cost = models.get(selected_model, "0")

    else:
        target_language = input(f"\n{lang.get('PROMPT_TARGET_LANGUAGE', '...')} ").lower().strip() or "en"
        profile['target_language'] = target_language
        models_path = "models.env"
        if not os.path.exists(models_path): print(f"HATA: '{models_path}' dosyası bulunamadı."); return
        models = {}
        with open(models_path, "r", encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith("#"): key, value = line.strip().split('=', 1); models[key] = value
        print(f"\n--- {lang.get('HEADER_MODEL_SELECTION', '---')} ---")
        model_list = list(models.items())
        for i, (name, cost) in enumerate(model_list): print(f"[{i+1}] {name} {lang.get('INFO_CREDITS', '...').format(cost=cost)}")
        while True:
            try:
                choice = int(input(f"\n{lang.get('PROMPT_SELECT_MODEL', '...').format(min=1, max=len(model_list))} "))
                if 1 <= choice <= len(model_list):
                    selected_model, selected_cost = model_list[choice-1]
                    profile['model_name'] = selected_model
                    break
                else: print(lang.get('ERROR_INVALID_CHOICE', '...'))
            except ValueError: print(lang.get('ERROR_VALUE_ERROR', '...'))
    
    print(f"\n--- {lang.get('HEADER_ARCHIVE_SELECTION', '---')} ---")
    archive_files = find_all_archives('.', lang)
    if not archive_files:
        print(lang.get('ERROR_NO_ARCHIVES_FOUND', '...'))
        return

    print(lang.get('INFO_ARCHIVES_FOUND', '...'))
    for i, file_path in enumerate(archive_files):
        print(f"[{i+1}] {file_path}")
    
    filepath = ""
    while True:
        try:
            choice = int(input(f"\n{lang.get('PROMPT_SELECT_AN_ARCHIVE', '...').format(min=1, max=len(archive_files))} "))
            if 1 <= choice <= len(archive_files):
                filepath = archive_files[choice-1]
                break
            else:
                print(lang.get('ERROR_INVALID_CHOICE', '...'))
        except ValueError:
            print(lang.get('ERROR_VALUE_ERROR', '...'))
    
    if not filepath:
        print(lang.get('INFO_ACTION_CANCELLED', '...')); return

    file_ext = os.path.splitext(filepath)[1].lower()
    
    if file_ext == '.epub':
        confirm = input(f"\n{lang.get('WARN_EPUB_EXPERIMENTAL', '...')}").lower()
        if confirm not in ['e', 'evet', 'y', 'yes']:
            print(lang.get('INFO_ACTION_CANCELLED', '...')); return
            
    if not profile_exists:
        save_profile(profile)
        print(f"\n{lang.get('INFO_PROFILE_CREATED', '...')}")

    with tempfile.TemporaryDirectory() as temp_dir:
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir)
        print(lang.get('INFO_EXTRACTING', '...').format(filename=os.path.basename(filepath)))
        image_map = None
        try:
            if file_ext == '.pdf': core_logic.extract_pdf(filepath, extract_dir)
            elif file_ext in ('.cbz', '.zip'): core_logic.extract_zip(filepath, extract_dir)
            elif file_ext in ('.cbr', '.rar'): core_logic.extract_rar(filepath, extract_dir)
            elif file_ext in ('.cb7', '.7z'): core_logic.extract_7z(filepath, extract_dir)
            elif file_ext == '.epub': image_map = core_logic.extract_epub(filepath, extract_dir)
            else: print(f"Desteklenmeyen dosya formatı: {file_ext}"); return
        except Exception as e:
            print(f"Dosya çıkarılırken hata oluştu: {e}"); return
        
        extracted_files = core_logic.find_all_images(extract_dir)
        print(lang.get('INFO_EXTRACTING_SUCCESS', '...').format(count=len(extracted_files)))
        
        print(f"\n--- {lang.get('HEADER_PREPROCESS', '---')} ---")
        images_to_process = []
        for img_path in extracted_files:
            if core_logic.preprocess_image(img_path, extract_dir, lang):
                images_to_process.append(img_path)

        image_count = len(images_to_process)
        print(f"\n--- {lang.get('HEADER_COST_CONFIRM', '---')} ---")
        if image_count == 0:
            print(f"Arşiv içinde çevrilecek resim bulunamadı."); return
            
        print(lang.get('INFO_FOLDER_SELECTED', "...").format(folder=os.path.basename(filepath), count=image_count))
        print(lang.get('INFO_MODEL_SELECTED', '...').format(model_name=selected_model))
        
        cost_per_image_str = selected_cost.replace('+', '')
        if cost_per_image_str.isdigit():
            cost_per_image = int(cost_per_image_str)
            total_cost = image_count * cost_per_image
            if '+' in selected_cost:
                print(lang.get('INFO_BASE_COST_ESTIMATE', '...').format(count=image_count, base_cost=cost_per_image, total_cost=total_cost))
            else:
                print(lang.get('INFO_TOTAL_COST', '...').format(count=image_count, cost_per_image=cost_per_image, total_cost=total_cost))
        
        run_workflow = False
        while True:
            confirm = input(f"\n{lang.get('PROMPT_CONFIRM_ACTION', '...')} ").lower()
            if confirm in ['e', 'evet', 'y', 'yes']: run_workflow = True; break
            elif confirm in ['h', 'hayır', 'n', 'no']: print(lang.get('INFO_ACTION_CANCELLED', '...')); break

        if not run_workflow:
            return

        print(f"\n--- {lang.get('HEADER_TRANSLATION_START', '---')} ---")
        translated_folder = os.path.join(extract_dir, "translated")
        os.makedirs(translated_folder, exist_ok=True)
        error_folder = os.path.join(extract_dir, "error")

        for i, file_path in enumerate(images_to_process):
            print(lang.get('INFO_PROCESSING', '...').format(i=i+1, total=len(images_to_process), filename=os.path.basename(file_path)))
            core_logic.process_single_file(file_path, api_key, selected_model, target_language, extract_dir, translated_folder, error_folder, lang)
            time.sleep(0.1)

        base_name = os.path.splitext(os.path.basename(filepath))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        output_dir = "archive_outputs"
        os.makedirs(output_dir, exist_ok=True)
        
        repack_success = False
        try:
            if file_ext == '.pdf':
                output_filename = os.path.join(output_dir, f"{base_name}_output_{timestamp}.pdf")
                print(lang.get('INFO_REPACKING', '...').format(output_filename=os.path.basename(output_filename)))
                core_logic.repack_pdf(translated_folder, output_filename)
                repack_success = True
            elif file_ext in ('.cbz', '.zip', '.cbr', '.rar', '.cb7', '.7z'):
                output_filename = os.path.join(output_dir, f"{base_name}_output_{timestamp}.cbz")
                print(lang.get('INFO_REPACKING', '...').format(output_filename=os.path.basename(output_filename)))
                core_logic.repack_cbz(translated_folder, output_filename)
                repack_success = True
            elif file_ext == '.epub':
                output_filename = os.path.join(output_dir, f"{base_name}_output_{timestamp}.epub")
                print(lang.get('INFO_REPACKING_EPUB', '...'))
                core_logic.repack_epub(filepath, translated_folder, image_map, output_filename)
                repack_success = True
            
            if repack_success: print(lang.get('INFO_REPACKING_SUCCESS', '...'))
        except Exception as e:
            print(f"Dosya yeniden paketlenirken bir hata oluştu: {e}")

    print(f"\n{lang.get('INFO_CLEANING_UP', '...')} ")
