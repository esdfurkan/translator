import os
import sys
import getpass
import time
import json
from dotenv import load_dotenv
import core_logic

def start_cli(lang, profile):
    print("--- Klasör Çevirme Aracı ---")
    
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

    print(f"\n--- {lang.get('HEADER_FOLDER_SELECTION', '---')} ---")
    subfolders = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith(('.', 'lang'))]
    if not subfolders:
        print(lang.get('ERROR_NO_SUBFOLDERS', '...')); return
    for i, folder_name in enumerate(subfolders): print(f"[{i+1}] {folder_name}")
    while True:
        try:
            choice = int(input(f"\n{lang.get('PROMPT_SELECT_FOLDER', '...').format(min=1, max=len(subfolders))} "))
            if 1 <= choice <= len(subfolders): selected_folder = subfolders[choice-1]; break
            else: print(lang.get('ERROR_INVALID_CHOICE', '...'))
        except ValueError: print(lang.get('ERROR_VALUE_ERROR', '...'))

    all_image_paths = core_logic.find_all_images(selected_folder)
    
    print(f"\n--- {lang.get('HEADER_PREPROCESS', '---')} ---")
    images_to_process = []
    for img_path in all_image_paths:
        if core_logic.preprocess_image(img_path, selected_folder, lang):
            images_to_process.append(img_path)
    
    image_count = len(images_to_process)
    
    print(f"\n--- {lang.get('HEADER_COST_CONFIRM', '---')} ---")
    if image_count == 0:
        print(f"'{selected_folder}' klasöründe ve alt klasörlerinde çevrilecek resim dosyası bulunamadı."); return
    
    print(lang.get('INFO_FOLDER_SELECTED', "...").format(folder=selected_folder, count=image_count))
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
    
    if run_workflow:
        if not profile_exists:
            with open('profile.json', 'w', encoding='utf-8') as f: json.dump(profile, f, indent=4)
            print(f"\n{lang.get('INFO_PROFILE_CREATED', '...')}")

        print(f"\n--- {lang.get('HEADER_TRANSLATION_START', '---')} ---")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_folder = f"{selected_folder}_output_{timestamp}"
        error_folder = os.path.join(selected_folder, "error")
        os.makedirs(output_folder, exist_ok=True)
        
        for i, file_path in enumerate(images_to_process):
            relative_path = os.path.relpath(file_path, selected_folder)
            print(lang.get('INFO_PROCESSING', '...').format(i=i+1, total=image_count, filename=relative_path))
            core_logic.process_single_file(file_path, api_key, selected_model, target_language, selected_folder, output_folder, error_folder, lang)
            time.sleep(0.1)
        
        print(f"\n--- {lang.get('HEADER_TRANSLATION_DONE', '---')} ---")
