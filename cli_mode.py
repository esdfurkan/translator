import os
import sys
import getpass
import subprocess
import configparser
from dotenv import load_dotenv
import core_logic

def start_cli(lang):
    config = configparser.ConfigParser()
    config.read('config.ini')
    NEXTCLOUD_ENABLED = config.getboolean('Features', 'nextcloud_enabled', fallback=False)

    api_key = ""
    api_env_path = "api.env"
    load_dotenv(dotenv_path=api_env_path)
    saved_api_key = os.getenv("API_KEY")

    if saved_api_key:
        print(lang.get('INFO_API_KEY_FOUND', 'Saved API key found and will be used.'))
        api_key = saved_api_key
    else:
        api_key = getpass.getpass(lang.get('PROMPT_API_KEY', 'Please enter your API Key and press Enter: ') + " ")
        if not api_key.strip():
            print(lang.get('ERROR_API_KEY_EMPTY', 'API Key not provided. Exiting program.'))
            return
        
        while True:
            save_confirm = input(f"\n{lang.get('PROMPT_SAVE_API_KEY', 'Do you want to save this API key for future use? (Y/N): ')} ").lower()
            if save_confirm in ['e', 'evet', 'y', 'yes']:
                with open(api_env_path, "w", encoding='utf-8') as f:
                    f.write(f"API_KEY={api_key}\n")
                print(lang.get('INFO_API_KEY_SAVED', 'API key saved to api.env.'))
                break
            elif save_confirm in ['h', 'hayır', 'n', 'no']:
                break
    
    target_language = input(f"\n{lang.get('PROMPT_TARGET_LANGUAGE', 'Enter the target language for the translation (e.g., en, es, ja):')} ").lower().strip() or "en"

    models_path = "models.env"
    if not os.path.exists(models_path):
        print(f"HATA: '{models_path}' dosyası bulunamadı.")
        return
    models = {}
    with open(models_path, "r", encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split('=', 1)
                models[key] = value

    print(f"\n--- {lang.get('HEADER_MODEL_SELECTION', '--- Model Selection ---')} ---")
    model_list = list(models.items())
    for i, (name, cost) in enumerate(model_list):
        print(f"[{i+1}] {name} {lang.get('INFO_CREDITS', '(Credits: {cost})').format(cost=cost)}")
    while True:
        try:
            choice = int(input(f"\n{lang.get('PROMPT_SELECT_MODEL', 'Please select a model ({min}-{max}): ').format(min=1, max=len(model_list))} "))
            if 1 <= choice <= len(model_list):
                selected_model, selected_cost = model_list[choice-1]
                break
            else:
                print(lang.get('ERROR_INVALID_CHOICE', 'Invalid choice.'))
        except ValueError:
            print(lang.get('ERROR_VALUE_ERROR', 'Please enter only a number.'))

    print(f"\n--- {lang.get('HEADER_FOLDER_SELECTION', '--- Folder Selection ---')} ---")
    subfolders = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.')]
    if not subfolders:
        print(lang.get('ERROR_NO_SUBFOLDERS', 'ERROR: No subfolders found.'))
        return
    for i, folder_name in enumerate(subfolders):
        print(f"[{i+1}] {folder_name}")
    while True:
        try:
            choice = int(input(f"\n{lang.get('PROMPT_SELECT_FOLDER', 'Please select a folder ({min}-{max}): ').format(min=1, max=len(subfolders))} "))
            if 1 <= choice <= len(subfolders):
                selected_folder = subfolders[choice-1]
                break
            else:
                print(lang.get('ERROR_INVALID_CHOICE', 'Invalid choice.'))
        except ValueError:
            print(lang.get('ERROR_VALUE_ERROR', 'Please enter only a number.'))

    core_logic.preprocess_and_compress_images(selected_folder, lang)

    print(f"\n--- {lang.get('HEADER_COST_CONFIRM', '--- Cost Calculation and Confirmation ---')} ---")
    image_files = [f for f in os.listdir(selected_folder) if f.lower().endswith(core_logic.GECERLI_UZANTILAR)]
    image_count = len(image_files)
    if image_count == 0:
        print(f"'{selected_folder}' klasöründe çevrilecek resim dosyası bulunamadı.")
        return
    print(lang.get('INFO_FOLDER_SELECTED', "Selected Folder: '{folder}' ({count} image(s) found)").format(folder=selected_folder, count=image_count))
    print(lang.get('INFO_MODEL_SELECTED', 'Selected Model: {model_name}').format(model_name=selected_model))
    if '+' in selected_cost:
        base_cost = int(selected_cost.replace('+', ''))
        print(lang.get('INFO_BASE_COST_ESTIMATE', '...').format(count=image_count, base_cost=base_cost, total_cost=image_count * base_cost))
    else:
        cost_per_image = int(selected_cost)
        print(lang.get('INFO_TOTAL_COST', '...').format(count=image_count, cost_per_image=cost_per_image, total_cost=image_count * cost_per_image))
    
    run_workflow = False
    while True:
        confirm = input(f"\n{lang.get('PROMPT_CONFIRM_ACTION', 'Do you approve this operation? (Y/N): ')} ").lower()
        if confirm in ['e', 'evet', 'y', 'yes']:
            run_workflow = True
            break
        elif confirm in ['h', 'hayır', 'n', 'no']:
            print(lang.get('INFO_ACTION_CANCELLED', 'Operation cancelled.'))
            break
    
    if run_workflow:
        output_folder_path, success = core_logic.process_images(api_key, selected_model, selected_folder, lang, target_language)
        
        path_for_upload = output_folder_path
        zip_file_created = False
        
        if os.path.exists("compress.sh") and os.access("compress.sh", os.X_OK):
            print(f"\n--- {lang.get('HEADER_COMPRESSION', '--- Compression ---')} ---")
            while True:
                comp_confirm = input(f"{lang.get('PROMPT_CONFIRM_COMPRESSION', '...').format(folder=output_folder_path)} ").lower()
                if comp_confirm in ['e', 'evet', 'y', 'yes']:
                    zip_filename = f"{output_folder_path}.zip"
                    print(f"{lang.get('INFO_CREATING_ZIP', '...').format(zip_filename=zip_filename)}")
                    try:
                        subprocess.run(["./compress.sh", output_folder_path, zip_filename], check=True, capture_output=True, text=True)
                        path_for_upload = zip_filename
                        zip_file_created = True
                        print(lang.get('INFO_COMPRESSION_SUCCESS', '...').format(zip_filename=zip_filename))
                    except subprocess.CalledProcessError as e:
                        print(f"Sıkıştırma hatası: {e.stderr}")
                    except Exception as e:
                        print(f"Sıkıştırma hatası: {e}")
                    break
                elif comp_confirm in ['h', 'hayır', 'n', 'no']:
                    print(lang.get('INFO_COMPRESSION_STEP_SKIPPED', '...'))
                    break

        nextcloud_link = None
        if NEXTCLOUD_ENABLED and os.path.exists("nextcloud.env"):
             while True:
                prompt_key = 'PROMPT_CONFIRM_UPLOAD_ZIP' if zip_file_created else 'PROMPT_CONFIRM_UPLOAD_FOLDER'
                upload_prompt = lang.get(prompt_key, 'Upload?').format(path=os.path.basename(path_for_upload))
                upload_confirm = input(f"\n{upload_prompt} ").lower()
                if upload_confirm in ['e', 'evet', 'y', 'yes']:
                    nextcloud_link = core_logic.upload_to_nextcloud(path_for_upload, lang)
                    break
                elif upload_confirm in ['h', 'hayır', 'n', 'no']:
                    break
        
        core_logic.send_notification(lang, success, selected_folder, nextcloud_link)
