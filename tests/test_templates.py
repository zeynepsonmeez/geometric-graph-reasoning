"""Problem şablonlarının şemaya ve taksonomiye uygunluğu."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import problem_templates as pt  # noqa: E402

SCHEMA_PATH = ROOT / "schema" / "problem_template.schema.json"
TEMPLATES = pt.load_all()

#: docs/taksonomi.md §5 — her hata sınıfı en az iki farklı aileden beslenmelidir.
MIN_FAMILIES_PER_CLASS = 2


def test_sablonlar_bulundu() -> None:
    assert TEMPLATES, "data/problems/ altinda hic sablon yok"


@pytest.mark.parametrize("path", sorted((ROOT / "data" / "problems").glob("P?-T??.json")))
def test_semaya_uygun(path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    instance = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.validate(instance, schema)


def test_ic_tutarlilik() -> None:
    sorunlar = pt.check_all(TEMPLATES)
    assert not sorunlar, "Sablon tutarsizliklari:\n" + "\n".join(f"  - {s}" for s in sorunlar)


def test_her_aile_temsil_ediliyor() -> None:
    """P1–P6'nin tamami kapsanmali (docs/taksonomi.md §5)."""
    eksik = {f"P{i}" for i in range(1, 7)} - {t.family for t in TEMPLATES}
    assert not eksik, f"Sablonu olmayan aileler: {sorted(eksik)}"


def test_her_hata_sinifi_en_az_iki_aileden_besleniyor() -> None:
    """Sinif ile problem ailesi arasinda yapay korelasyon olusmamali.

    Tek aileye bagli bir hata sinifi olsaydi, model problem tipini taniyarak
    hata sinifini bilebilirdi (docs/taksonomi.md §5).
    """
    aileler: dict[str, set[str]] = {}
    for t in TEMPLATES:
        for v in t.varyantlar:
            if v.sinif != "H0":
                aileler.setdefault(v.sinif, set()).add(t.family)

    for sinif in ("H1", "H2", "H3"):
        bulunan = aileler.get(sinif, set())
        assert len(bulunan) >= MIN_FAMILIES_PER_CLASS, (
            f"{sinif} yalnizca {sorted(bulunan) or 'hicbir'} ailesinden besleniyor; "
            f"en az {MIN_FAMILIES_PER_CLASS} aile gerekli"
        )


def test_h1_varyantlari_verilen_iddiasi_iceriyor() -> None:
    """H1 ile H3 ayrimi 'verilen' iddiasinin varligina dayanir (§4.2)."""
    for t in TEMPLATES:
        for v in t.varyantlar:
            if v.sinif != "H1":
                continue
            kurallar = {s["rule"] for s in v.steps}
            assert "verilen" in kurallar, (
                f"{t.template_id}/H1: 'verilen' kurali kullanan adim yok. "
                f"Bu varyant taksonomi §4.2'ye gore H3 olarak etiketlenmeliydi."
            )


def test_h3_varyantlari_verilen_iddiasi_icermiyor() -> None:
    """H3'te ogrenci eksik kosulu hic anmaz (§4.2)."""
    for t in TEMPLATES:
        for v in t.varyantlar:
            if v.sinif != "H3":
                continue
            kurallar = {s["rule"] for s in v.steps}
            assert "verilen" not in kurallar, (
                f"{t.template_id}/H3: 'verilen' kurali kullaniliyor. "
                f"Bu varyant taksonomi §4.2'ye gore H1 olmali."
            )


def test_hatali_adim_konumu_cesitli() -> None:
    """Hata hep ilk adimda olamaz; yoksa M3 metrigi anlamsizlasir.

    docs/taksonomi.md §7 — uretec kisitlari.
    """
    konumlar = Counter()
    for t in TEMPLATES:
        for v in t.varyantlar:
            if v.hatali_adim is None:
                continue
            ids = [s["id"] for s in v.steps]
            konumlar[ids.index(v.hatali_adim)] += 1

    assert len(konumlar) >= 2, (
        f"Hatali adim her zaman ayni konumda: {dict(konumlar)}. "
        f"Model 'ilk adimi soyle' diyerek yuksek M3 skoru alir."
    )


def test_kazanim_kodlari_uydurulmamis() -> None:
    """MEB kodlari birincil kaynaktan alinana kadar null kalmali.

    Bu test, kodlar dolduruldugunda bicimsel bir hatirlaticiya donusur:
    elle girilen her kod bilincli bir karardir.
    """
    for t in TEMPLATES:
        if t.kazanim_kodu is not None:
            assert t.kazanim_kodu.strip(), f"{t.template_id}: bos kazanim_kodu"
