import os
import sys
import configparser

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def select_language():
    lang_dir = "lang"
    if not os.path.isdir(lang_dir):
        print("FATAL: 'lang' directory not found.")
        sys.exit(1)
    languages = [f for f in os.listdir(lang_dir) if f.endswith('.ini')]
    if not languages:
        print(f"FATAL: No language (.ini) files found in '{lang_dir}' directory.")
        sys.exit(1)
    
    print("--- Dil Seçimi / Language Selection ---")
    lang_map = {}
    for i, lang_file in enumerate(languages):
        lang_code = os.path.splitext(lang_file)[0]
        lang_map[i+1] = lang_file
        print(f"[{i+1}] {lang_code}")
    while True:
        try:
            choice = int(input("\nLütfen bir dil seçin / Please select a language: "))
            if choice in lang_map:
                return os.path.join(lang_dir, lang_map[choice])
            else:
                print("Geçersiz seçim. / Invalid choice.")
        except ValueError:
            print("Lütfen bir sayı girin. / Please enter a number.")

def load_language_strings(lang_file_path):
    config = configparser.ConfigParser()
    config.read(lang_file_path, encoding='utf-8')
    return config['strings']

def main():
    clear_screen()
    selected_lang_file = select_language()
    lang = load_language_strings(selected_lang_file)
    
    clear_screen()
    
    try:
        import cli_mode
        import bot_mode
    except ImportError as e:
        print(f"HATA: Gerekli modüller bulunamadı: {e}")
        print("Lütfen tüm .py dosyalarının aynı dizinde olduğundan emin olun.")
        return

    while True:
        print(f"\n{lang.get('HEADER_MAIN_MENU', '--- Translation Automation System ---')}")
        print(lang.get('PROMPT_SELECT_MODE_CLI', '[1] Step-by-Step Translation (For one-time jobs)'))
        print(lang.get('PROMPT_SELECT_MODE_BOT', '[2] Start Automatic Bot (Listens for links from chat)'))
        print(f"\n{lang.get('PROMPT_EXIT', 'Press [Q] to exit.')}")
        
        choice = input(f"\n{lang.get('PROMPT_CHOICE', 'Your choice: ')}").lower().strip()

        if choice == '1':
            cli_mode.start_cli(lang)
            break
        elif choice == '2':
            bot_mode.start_bot(lang)
            break
        elif choice == 'q':
            break
        else:
            clear_screen()
            print(f"{lang.get('ERROR_INVALID_CHOICE', 'Invalid choice.')}\n")
    
    print(f"\n{lang.get('INFO_ALL_DONE', 'All operations are finished. Exiting program.')}")

if __name__ == "__main__":
    main()
