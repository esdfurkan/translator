#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "Hata: Yanlış kullanım."
    echo "Kullanım: $0 [Sıkıştırılacak Klasör/Dosya] [Çıktı Dosya Adı]"
    exit 1
fi

if ! command -v 7z &> /dev/null; then
    echo "HATA: '7z' komutu bulunamadı."
    echo "Lütfen 'p7zip-full' paketini kurun."
    echo "Debian/Ubuntu için: sudo apt install p7zip-full"
    exit 1
fi

KAYNAK="$1"
HEDEF_DOSYA="$2"

CEKIRDEK_SAYISI=$(nproc)
if [ "$CEKIRDEK_SAYISI" -gt 1 ]; then
    KULLANILACAK_CEKIRDEK=$(($CEKIRDEK_SAYISI - 1))
else
    KULLANILACAK_CEKIRDEK=1
fi

echo "Sıkıştırma başlıyor..."
echo "Kaynak: $KAYNAK"
echo "Hedef: $HEDEF_DOSYA"
echo "Kullanılacak İşlemci Çekirdeği: $KULLANILACAK_CEKIRDEK"

7z a -tzip -mmt="$KULLANILACAK_CEKIRDEK" -r "$HEDEF_DOSYA" "$KAYNAK"

echo "Sıkıştırma başarıyla tamamlandı!"
