import os
import sys
import hashlib
import argparse
import fnmatch

IGNORE_PATTERNS = [
    '__pycache__',
    '*.pyc',
    '*_output_*',
    'error',
    'log.txt',
    '*.tmp.jpg',
    '*.zip',
    '.git',
    '.vscode',
    'api.env', 
]

def should_ignore(path, output_filename):
    path_parts = path.split(os.sep)
    if os.path.basename(path) == output_filename:
        return True
    for part in path_parts:
        for pattern in IGNORE_PATTERNS:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except IOError:
        return None

def create_hashes(target_path, output_file):
    if not os.path.exists(target_path):
        print(f"Hata: Belirtilen yol bulunamadı: {target_path}")
        return

    hash_records = []
    base_dir = os.path.abspath(target_path)
    output_filepath = os.path.abspath(os.path.join(base_dir, output_file))

    print(f"'{base_dir}' klasörü taranıyor...")
    for root, dirs, files in os.walk(base_dir, topdown=True):
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d), os.path.basename(output_filepath))]
        
        for filename in files:
            file_path = os.path.join(root, filename)
            if should_ignore(file_path, os.path.basename(output_filepath)):
                continue

            relative_path = os.path.relpath(file_path, base_dir)
            file_hash = calculate_sha256(file_path)
            if file_hash:
                hash_records.append(f"{file_hash}  {relative_path.replace(os.sep, '/')}")

    if not hash_records:
        print("Hash'i hesaplanacak dosya bulunamadı.")
        return

    try:
        with open(output_filepath, "w", encoding='utf-8') as f:
            f.write("\n".join(sorted(hash_records)) + "\n")
        print(f"Başarılı! {len(hash_records)} dosya için hash listesi oluşturuldu: {output_file}")
    except IOError as e:
        print(f"Hata: Hash dosyası yazılamadı: {e}")

def check_hashes(hash_file):
    if not os.path.isfile(hash_file):
        print(f"Hata: Hash dosyası bulunamadı: {hash_file}")
        return

    print(f"'{hash_file}' kullanılarak dosya bütünlüğü kontrol ediliyor...")
    base_dir = os.path.dirname(os.path.abspath(hash_file))
    all_ok = True
    found_files = set()
    
    with open(hash_file, "r", encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    if not lines:
        print("Hash dosyasında kontrol edilecek kayıt bulunamadı.")
        return

    for line in lines:
        try:
            expected_hash, relative_path = line.split('  ', 1)
            file_path = os.path.join(base_dir, relative_path.replace('/', os.sep))
            found_files.add(os.path.abspath(file_path))

            if not os.path.exists(file_path):
                print(f"EKSİK: {relative_path}")
                all_ok = False
                continue

            current_hash = calculate_sha256(file_path)
            if current_hash == expected_hash:
                print(f"OK: {relative_path}")
            else:
                print(f"DEĞİŞTİRİLMİŞ: {relative_path}")
                all_ok = False
        except ValueError:
            print(f"UYARI: Hatalı formatlı satır atlanıyor: {line}")

    print("-" * 20)
    if all_ok:
        print("Tüm kod dosyaları başarıyla doğrulandı.")
    else:
        print("Bazı kod dosyalarında bütünlük sorunları tespit edildi.")

def main():
    parser = argparse.ArgumentParser(description="Proje kod dosyaları için SHA-256 hash listesi oluşturur veya kontrol eder.")
    subparsers = parser.add_subparsers(dest='command', required=True, help="Çalıştırılacak komut")

    create_parser = subparsers.add_parser('create', help="Mevcut dizindeki kod dosyaları için bir hash listesi oluşturur.")
    create_parser.add_argument('-o', '--output', type=str, default="checksums.sha256", help="Çıktı hash dosyasının adı (varsayılan: checksums.sha256).")

    check_parser = subparsers.add_parser('check', help="Bir hash listesi dosyasını kullanarak bütünlüğü kontrol eder.")
    check_parser.add_argument('hashfile', type=str, nargs='?', default="checksums.sha256", help="Kontrol edilecek hash listesi (varsayılan: checksums.sha256).")

    args = parser.parse_args()

    if args.command == 'create':
        create_hashes('.', args.output)
    elif args.command == 'check':
        check_hashes(args.hashfile)

if __name__ == "__main__":
    main()
