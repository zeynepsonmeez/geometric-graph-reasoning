"""Türkçe ek uyumu.

Arayüz ve geri bildirim metinleri kelimelere ek getiriyor: "[AH] bir
yükseklik**tir**", "[CN] kenarortay**dır**". Ek sabit yazılırsa ünlü uyumu ve
ünsüz benzeşmesi bozulur ve "yüksekliktır", "kenarortaytir" gibi çıktılar
oluşur — matematik öğretmenine gösterilen bir arayüzde ilk göze çarpan şey budur.

Bu modül yalnızca metin üretir; hiçbir alan modülünü import etmez, dolayısıyla
mimarideki bağımsızlık kurallarını etkilemez.
"""

from __future__ import annotations

#: Kalın/ince ve düz/yuvarlak ayrımına göre ekin alacağı ünlü.
_UNLU_ESLEMESI = {
    "a": "ı", "ı": "ı",
    "e": "i", "i": "i",
    "o": "u", "u": "u",
    "ö": "ü", "ü": "ü",
}

#: Sert ünsüzden sonra ek sertleşir (ünsüz benzeşmesi): -dir → -tir.
SERT_UNSUZLER = set("fstkçşhp")


def _son_unlu(kelime: str) -> str | None:
    for harf in reversed(kelime.lower()):
        if harf in _UNLU_ESLEMESI:
            return harf
    return None


def ek_dir(kelime: str) -> str:
    """Kelimeye uygun '-dir' ekini döndürür.

    >>> ek_dir("yükseklik")
    'tir'
    >>> ek_dir("kenarortay")
    'dır'
    >>> ek_dir("açıortay")
    'dır'
    """
    temiz = kelime.strip().rstrip(".,;:!?")
    if not temiz:
        return "dir"

    unlu = _son_unlu(temiz)
    ek_unlusu = _UNLU_ESLEMESI.get(unlu or "", "i")
    bas = "t" if temiz.lower()[-1] in SERT_UNSUZLER else "d"
    return f"{bas}{ek_unlusu}r"


def dir(kelime: str) -> str:
    """Kelimeyi ekiyle birlikte döndürür: 'yükseklik' -> 'yüksekliktir'."""
    return f"{kelime}{ek_dir(kelime)}"
