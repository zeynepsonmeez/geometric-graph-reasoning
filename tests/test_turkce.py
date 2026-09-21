"""Türkçe ek uyumu.

Arayüz metinleri matematik öğretmenine gösterilecek; "yüksekliktır" gibi bir
çıktı ilk göze çarpan şey olur. Ek sabit yazılmamalı.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import turkce  # noqa: E402


@pytest.mark.parametrize(
    "kelime,beklenen",
    [
        ("yükseklik", "yüksekliktir"),   # ince ünlü + sert ünsüz
        ("kenarortay", "kenarortaydır"), # kalın ünlü + yumuşak ünsüz
        ("açıortay", "açıortaydır"),
        ("kenar", "kenardır"),
        ("üçgen", "üçgendir"),
        ("uzunluk", "uzunluktur"),       # yuvarlak ünlü
        ("benzerlik", "benzerliktir"),
    ],
)
def test_ek_uyumu(kelime: str, beklenen: str) -> None:
    assert turkce.dir(kelime) == beklenen


def test_bos_kelimede_patlamaz() -> None:
    assert turkce.ek_dir("") == "dir"


def test_noktalama_temizlenir() -> None:
    assert turkce.ek_dir("yükseklik.") == "tir"


def test_unlu_yoksa_varsayilan() -> None:
    assert turkce.ek_dir("xyz").endswith("r")


def test_arayuzde_sabit_ek_kalmadi() -> None:
    """Ek sabit yazilirsa uyum bozulur; tek kaynak turkce.py olmali."""
    import re

    hedefler = [
        ROOT / "app.py",
        ROOT / "src" / "feedback.py",
        ROOT / "src" / "llm_checker.py",
        ROOT / "pages" / "2_Etiketle.py",
    ]
    kalip = re.compile(r"\{tip\}t[ıi]r|\}\*\*t[ıi]r")

    for yol in hedefler:
        if not yol.exists():
            continue
        for i, satir in enumerate(yol.read_text(encoding="utf-8").split("\n"), 1):
            assert not kalip.search(satir), (
                f"{yol.name}:{i} sabit ek kullaniyor: {satir.strip()}"
            )
