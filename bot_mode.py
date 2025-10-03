import os
import sys
import asyncio
import discord
import requests
import urllib.parse
import tempfile
import zipfile
from dotenv import load_dotenv
import configparser
import core_logic

def load_bot_language(lang_code='tr'):
    try:
        lang_dir = "lang"
        lang_file = f"{lang_code}.ini"
        lang_path = os.path.join(lang_dir, lang_file)
        if not os.path.exists(lang_path):
            print(f"WARNING: '{lang_path}' not found. Using default text.")
            return {}
        
        config = configparser.ConfigParser()
        config.read(lang_path, encoding='utf-8')
        return config['strings']
    except Exception as e:
        print(f"Error loading language file: {e}")
        return {}

async def download_file(url, target_path):
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException:
        return False

def start_bot(lang):
    load_dotenv(dotenv_path="bot.env")
    BOT_LANGUAGE = os.getenv("BOT_LANGUAGE", "tr")
    BOT_TARGET_LANGUAGE = os.getenv("BOT_TARGET_LANGUAGE", "en")
    bot_lang = load_bot_language(BOT_LANGUAGE)
    
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
        print(bot_lang.get('ERROR_BOT_CONFIG_MISSING', 'Bot configuration is missing or incomplete in bot.env.'))
        return

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f'{client.user} olarak Discord\'a bağlandım.')
        print(f'Dinlenen Kanal ID: {DISCORD_CHANNEL_ID}')
        print('İstekler için hazırım...')

    @client.event
    async def on_message(message):
        if message.author == client.user or str(message.channel.id) != DISCORD_CHANNEL_ID:
            return

        url, original_filename = None, "dosya.zip"

        if message.attachments and message.attachments[0].filename.lower().endswith('.zip'):
            url, original_filename = message.attachments[0].url, message.attachments[0].filename
        else:
            try:
                parsed_url = urllib.parse.urlparse(message.content)
                if parsed_url.scheme in ['http', 'https'] and parsed_url.path.lower().endswith('.zip'):
                    url, original_filename = message.content, os.path.basename(parsed_url.path)
            except: pass

        if url:
            processing_message = await message.channel.send(f"✅ **İstek Alındı:** `{original_filename}`\nİşlem başlatılıyor...")
            
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    download_path = os.path.join(temp_dir, "downloaded.zip")
                    extract_folder = os.path.join(temp_dir, "extracted")
                    os.makedirs(extract_folder, exist_ok=True)
                    
                    await processing_message.edit(content=f"⏳ `{original_filename}` indiriliyor...")
                    if not await download_file(url, download_path):
                        await processing_message.edit(content=f"❌ **Hata:** `{original_filename}` indirilemedi.")
                        return

                    await processing_message.edit(content=f"⚙️ `{original_filename}` arşivden çıkarılıyor...")
                    with zipfile.ZipFile(download_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_folder)

                    load_dotenv(dotenv_path="api.env")
                    api_key = os.getenv("API_KEY")
                    if not api_key:
                        await processing_message.edit(content=f"❌ **Hata:** Sunucuda API anahtarı ayarlı değil (`api.env`).")
                        return
                    
                    await processing_message.edit(content=f"🖼️ Görüntüler sıkıştırılıyor...")
                    core_logic.preprocess_and_compress_images(extract_folder, bot_lang)
                    
                    await processing_message.edit(content=f"✍️ Çeviri işlemi API'ye gönderiliyor...")
                    output_folder, success = core_logic.process_images(api_key, "gemini-2.0-flash", extract_folder, bot_lang, BOT_TARGET_LANGUAGE)
                    
                    nextcloud_link = None
                    if success and os.path.exists("config.ini"):
                        config = configparser.ConfigParser()
                        config.read('config.ini')
                        if config.getboolean('Features', 'nextcloud_enabled', fallback=False):
                            await processing_message.edit(content=f"☁️ Sonuçlar Nextcloud'a yükleniyor...")
                            nextcloud_link = core_logic.upload_to_nextcloud(output_folder, bot_lang)

                    final_message = f"🎉 **İşlem Tamamlandı:** `{original_filename}`"
                    if nextcloud_link:
                        final_message += f"\n\n🔗 **Paylaşım Bağlantısı:** {nextcloud_link}"
                    else:
                        final_message += "\nSonuçlar sunucuya kaydedildi (Nextcloud entegrasyonu aktif değil)."
                    
                    await processing_message.edit(content=final_message)
                    core_logic.send_notification(bot_lang, True, original_filename, nextcloud_link)
            
            except Exception as e:
                error_message = f"❌ **Hata Oluştu!**\n`{original_filename}` işlenemedi.\n\n**Hata:** `{str(e)}`"
                await processing_message.edit(content=error_message)
                core_logic.send_notification(bot_lang, False, original_filename)

    client.run(DISCORD_BOT_TOKEN)
