"""Akıl yürütme grafı görselleştirmesinin denetimi.

Streamlit gerektirmez; `visualize` saf SVG döndürür.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import generator as gen  # noqa: E402
import verifier as vf  # noqa: E402
import visualize as viz  # noqa: E402

ADIMLAR = [
    {"id": "s1", "claim": "m(A) + m(B) + m(C) = 180", "rule": "ic_acilar_toplami", "depends_on": []},
    {"id": "s2", "claim": "m(B) = 90", "rule": "verilen", "depends_on": []},
    {"id": "s3", "claim": "|AC|^2 = 16 + 81", "rule": "pisagor", "depends_on": ["s2"]},
]


def test_bos_adim_listesi_patlamaz() -> None:
    svg = viz.reasoning_graph_svg([])
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_her_adim_cizilir() -> None:
    svg = viz.reasoning_graph_svg(ADIMLAR)
    for adim in ADIMLAR:
        assert f">{adim['id']}<" in svg or f">{adim['id']} ✗<" in svg


def test_hatali_adim_isaretlenir() -> None:
    svg = viz.reasoning_graph_svg(ADIMLAR, error_step="s2")
    assert ">s2 ✗<" in svg
    assert "#a3251f" in svg, "hata rengi kullanilmamis"


def test_kirlenmis_adimlar_bulunur() -> None:
    """s3, s2'ye bagli oldugu icin kirlenmistir (docs/taksonomi.md §4.1)."""
    assert viz._kirlenmisler(ADIMLAR, "s2") == {"s3"}


def test_kirlenme_zincir_boyunca_yayilir() -> None:
    zincir = [
        {"id": "s1", "claim": "", "rule": "verilen", "depends_on": []},
        {"id": "s2", "claim": "", "rule": "pisagor", "depends_on": ["s1"]},
        {"id": "s3", "claim": "", "rule": "pisagor", "depends_on": ["s2"]},
    ]
    assert viz._kirlenmisler(zincir, "s1") == {"s2", "s3"}


def test_hatasiz_cozumde_kirlenme_yok() -> None:
    assert viz._kirlenmisler(ADIMLAR, None) == set()


def test_bagimlilik_oklari_cizilir() -> None:
    svg = viz.reasoning_graph_svg(ADIMLAR)
    assert svg.count("<line") == 1, "s3 -> s2 baglantisi tek ok olmali"


def test_uzun_iddia_kisaltilir() -> None:
    uzun = [{"id": "s1", "claim": "x" * 200, "rule": "pisagor", "depends_on": []}]
    svg = viz.reasoning_graph_svg(uzun)
    assert "…" in svg
    assert "x" * 200 not in svg


def test_ozel_karakterler_kacirilir() -> None:
    """Iddia metni SVG'yi bozmamali."""
    tehlikeli = [{"id": "s1", "claim": "a < b & c > d", "rule": "r", "depends_on": []}]
    svg = viz.reasoning_graph_svg(tehlikeli)
    assert "&lt;" in svg and "&amp;" in svg
    assert "a < b &" not in svg


def test_gercek_orneklerle_calisir() -> None:
    for sol in gen.generate(total=40, seed=31)[:20]:
        bulgu = vf.verify_solution(sol)
        svg = viz.reasoning_graph_svg(sol["steps"], bulgu.error_step)
        assert svg.startswith("<svg")
        if bulgu.error_step:
            assert f">{bulgu.error_step} ✗<" in svg


def test_app_modulu_derlenir() -> None:
    """app.py sozdizimsel olarak gecerli mi? (Streamlit calistirmadan)"""
    import py_compile

    py_compile.compile(str(ROOT / "app.py"), doraise=True)
