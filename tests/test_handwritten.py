"""Elle yazılan küme altyapısının denetimi.

Küme henüz boş olabilir; testler bunu bir başarısızlık saymaz. Denetledikleri
şey **altyapının doğru çalıştığı** ve özellikle **körlüğün korunduğudur**.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

import agreement  # noqa: E402
import handwritten as hw  # noqa: E402
import verifier as vf  # noqa: E402

ORNEK = ROOT / "data" / "handwritten" / "ORNEK-FORMAT.json"


# --------------------------------------------------------------------------
# Körlük — protokolün kod düzeyinde zorlanması
# --------------------------------------------------------------------------


def test_cozum_semasi_label_alanini_reddeder() -> None:
    """Etiketin çözüm dosyasına sızması körlüğü bozar."""
    jsonschema = pytest.importorskip("jsonschema")
    schema = hw.unlabeled_schema()

    assert "label" not in schema["properties"]
    assert "label" not in schema["required"]

    sol = json.loads(ORNEK.read_text(encoding="utf-8"))
    sol.pop("_aciklama", None)
    sol["rendering"]["coords"] = {"K": [0, 0], "L": [1, 0], "M": [0, 1]}
    sol["label"] = {"error_class": "H1", "error_step": "s1", "source": "A1"}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(sol, schema)


def test_check_label_iceren_cozumu_yakalar() -> None:
    sol = json.loads(ORNEK.read_text(encoding="utf-8"))
    sol["label"] = {"error_class": "H1", "error_step": "s1", "source": "A1"}
    sorunlar = hw.check([sol])
    assert any("label" in s for s in sorunlar), sorunlar


def test_etiketler_cozumlerden_ayri_dizinde() -> None:
    assert hw.SOLUTIONS_DIR != hw.LABELS_DIR
    assert hw.LABELS_DIR.name == "labels"


# --------------------------------------------------------------------------
# Biçim örneği
# --------------------------------------------------------------------------


def test_ornek_format_kumeye_dahil_edilmez() -> None:
    """ORNEK- ile başlayan dosyalar yükleyici tarafından atlanmalı."""
    assert ORNEK.exists()
    assert ORNEK not in hw.solution_paths()


def test_ornek_format_semaya_uygun() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    sol = json.loads(ORNEK.read_text(encoding="utf-8"))
    dolu = hw.fill_rendering(sol)
    jsonschema.validate(dolu, hw.unlabeled_schema())


def test_ornek_format_dogrulayicidan_gecer() -> None:
    """Biçim örneği kasıtlı olarak H1'dir: diklik verilmemiş ama 'verilen' denmiş."""
    sol = json.loads(ORNEK.read_text(encoding="utf-8"))
    bulgu = vf.verify(sol["figure"], sol["steps"])
    assert bulgu.error_class == "H1"
    assert bulgu.error_step == "s1"


# --------------------------------------------------------------------------
# Çizim
# --------------------------------------------------------------------------


def test_fill_rendering_koordinat_uretir() -> None:
    sol = json.loads(ORNEK.read_text(encoding="utf-8"))
    dolu = hw.fill_rendering(sol)
    coords = dolu["rendering"]["coords"]
    for nokta in sol["figure"]["points"]:
        assert nokta in coords, f"{nokta} icin koordinat yok"


def test_fill_rendering_girdiyi_degistirmez() -> None:
    sol = json.loads(ORNEK.read_text(encoding="utf-8"))
    once = json.dumps(sol, sort_keys=True)
    hw.fill_rendering(sol)
    assert json.dumps(sol, sort_keys=True) == once


# --------------------------------------------------------------------------
# Mevcut küme (boş olabilir)
# --------------------------------------------------------------------------


def test_mevcut_kume_tutarli() -> None:
    sorunlar = hw.check() + hw.check_labels()
    assert not sorunlar, "Elle yazilan kumede sorun:\n" + "\n".join(
        f"  - {s}" for s in sorunlar
    )


# --------------------------------------------------------------------------
# Cohen kappa
# --------------------------------------------------------------------------


def test_kappa_tam_uyumda_bir() -> None:
    a = ["H0", "H1", "H2", "H3", "H1"]
    assert agreement.cohen_kappa(a, list(a)) == pytest.approx(1.0)


def test_kappa_sansa_gore_duzeltir() -> None:
    """Ham uyum yüksek olsa da şans düzeltmesi κ'yı düşürür."""
    a = ["H1"] * 9 + ["H0"]
    b = ["H1"] * 9 + ["H2"]
    kappa = agreement.cohen_kappa(a, b)
    assert kappa < 0.9, f"sans duzeltmesi uygulanmamis gorunuyor: {kappa}"


def test_rapor_bos_kumede_de_uretilir() -> None:
    rapor, ozet = agreement.build_report()
    assert isinstance(rapor, str) and rapor.strip()
    assert "Kodlayıcılar Arası Uyum" in rapor
    assert ozet["n"] == len(set(hw.load_labels("A1")) & set(hw.load_labels("A2")))


def test_kappa_yorumu_esikleri() -> None:
    assert agreement.interpret(0.85) == "neredeyse tam uyum"
    assert agreement.interpret(0.70) == "önemli düzeyde uyum"
    assert agreement.interpret(0.10) == "çok zayıf uyum"
