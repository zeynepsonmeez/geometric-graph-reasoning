"""Streamlit sayfalarının denetimi.

Streamlit çalıştırılmadan yapılabilecek iki şey denetlenir: sayfalar sözdizimsel
olarak geçerli mi, ve **körlük kurallarını ihlal eden bir çağrı içeriyorlar mı?**

İkincisi kritiktir. Körlük bir söz değil, kodun özelliği olmalıdır:

  - Örnek yazma sayfası hata sınıflarını göstermemeli — gönüllü sınıfları
    bilirse sınıfa göre örnek üretir ve küme sentetik derlemin kopyasına döner.
  - Etiketleme sayfası ne diğer kodlayıcının etiketini ne doğrulayıcının
    teşhisini göstermeli — ikisi de κ'yı ve doğrulayıcı-insan karşılaştırmasını
    geçersiz kılar.
"""

from __future__ import annotations

import ast
import py_compile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "pages"

YAZ = PAGES / "1_Ornek_yaz.py"
ETIKETLE = PAGES / "2_Etiketle.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    adlar: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            adlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            adlar.add(node.module.split(".")[0])
    return adlar


@pytest.mark.parametrize("path", sorted(PAGES.glob("*.py")))
def test_sayfa_derlenir(path: Path) -> None:
    py_compile.compile(str(path), doraise=True)


def test_sayfalar_mevcut() -> None:
    assert YAZ.exists() and ETIKETLE.exists()


# --------------------------------------------------------------------------
# Körlük — örnek yazma sayfası
# --------------------------------------------------------------------------


def test_yazma_sayfasi_hata_siniflarini_gostermez() -> None:
    """Gonullu H0-H3'u gormemeli; sinifa gore ornek uretmeye baslar."""
    metin = YAZ.read_text(encoding="utf-8")
    kod = "\n".join(
        satir for satir in metin.splitlines() if not satir.strip().startswith("#")
    )
    # Docstring'deki aciklama disinda H0..H3 gecmemeli
    govde = kod.split('"""', 2)[-1]
    for sinif in ("H1", "H2", "H3"):
        assert f'"{sinif}"' not in govde and f"'{sinif}'" not in govde, (
            f"Ornek yazma sayfasinda {sinif} sinifi geciyor; gonullu siniflari gormemeli."
        )


def test_yazma_sayfasi_dogrulayiciyi_kullanmaz() -> None:
    """Gonulluye 'bu cozum hatali' demek, hatayi duzeltmeye iter."""
    assert "verifier" not in _imports(YAZ)


# --------------------------------------------------------------------------
# Körlük — etiketleme sayfası
# --------------------------------------------------------------------------


def test_etiketleme_dogrulayiciyi_kullanmaz() -> None:
    """Kodlayici dogrulayicinin teshisini gorurse ona uyar.

    O zaman "dogrulayici insan etiketiyle ne kadar ortusuyor?" sorusu kendi
    kendini dogrulayan bir donguye doner.
    """
    assert "verifier" not in _imports(ETIKETLE), (
        "Etiketleme sayfasi verifier import ediyor; kodlayiciyi yonlendirir."
    )


def test_etiketleme_yalnizca_secili_kodlayiciyi_yukler() -> None:
    """Iki kodlayicinin etiketi ayni anda yuklenirse korluk kirilir."""
    metin = ETIKETLE.read_text(encoding="utf-8")
    assert metin.count("load_labels(") == 1, (
        "load_labels birden fazla yerde cagriliyor; digerinin etiketi sizabilir."
    )
    assert 'load_labels("A1")' not in metin and "load_labels('A1')" not in metin, (
        "Sabit kodlayici adiyla etiket yukleniyor; secili olan disindaki gorulebilir."
    )


def test_etiketleme_uretec_etiketini_gostermez() -> None:
    """Elle yazilan kumede uretec etiketi yoktur; yine de kod onu aramamali."""
    metin = ETIKETLE.read_text(encoding="utf-8")
    assert "error_class" in metin, "etiketleme sinif yazmali"
    assert '["label"]' not in metin and "'label'" not in metin, (
        "Cozum nesnesinden label okunuyor; elle yazilan kumede boyle bir alan olmamali."
    )


# --------------------------------------------------------------------------
# Kaydetme yolları
# --------------------------------------------------------------------------


def test_yazma_sayfasi_dogru_dizine_kaydeder() -> None:
    metin = YAZ.read_text(encoding="utf-8")
    assert "hw.SOLUTIONS_DIR" in metin
    assert "hw.LABELS_DIR" not in metin, "cozum yazan sayfa etiket dizinine yazmamali"


def test_etiketleme_dogru_dizine_kaydeder() -> None:
    metin = ETIKETLE.read_text(encoding="utf-8")
    assert "hw.LABELS_DIR" in metin
    assert "hw.SOLUTIONS_DIR" not in metin, "etiketleme cozum dosyalarini degistirmemeli"
