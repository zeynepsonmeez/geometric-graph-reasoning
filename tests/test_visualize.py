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


# --------------------------------------------------------------------------
# Çift graf — projenin tezini tek görselde anlatan öğe
# --------------------------------------------------------------------------


def _cift(sinif: str):
    import renderer

    sol = next(
        s for s in gen.generate(total=300, seed=555)
        if s["label"]["error_class"] == sinif
    )
    bulgu = vf.verify_solution(sol)
    fsvg = renderer.to_svg(
        sol["figure"], sol["rendering"]["coords"], sol["rendering"]["note"]
    )
    return sol, bulgu, viz.dual_graph_svg(
        sol["figure"], fsvg, sol["steps"], bulgu.error_step, bulgu.error_class
    )


def test_cift_graf_iki_paneli_de_etiketler() -> None:
    _, _, svg = _cift("H1")
    assert "ŞEKİL GRAFI" in svg and "AKIL YÜRÜTME GRAFI" in svg
    assert "ne verildi?" in svg and "nasıl ilerledi?" in svg


def test_cift_graf_sekli_gomer() -> None:
    """Cizim motorunun ciktisi yeniden uretilmez, ic ice SVG olarak gomulur."""
    sol, _, svg = _cift("H1")
    assert svg.count("<svg") == 2, "sekil gomulu degil"
    for nokta in sol["figure"]["points"]:
        assert f">{nokta}<" in svg


def test_tutarsizlik_rozeti_hata_sinifina_gore_degisir() -> None:
    for sinif, beklenen in viz.EKSIK_METNI.items():
        _, bulgu, svg = _cift(sinif)
        assert bulgu.error_class == sinif
        assert beklenen in svg, f"{sinif}: '{beklenen}' rozeti yok"


def test_hatasiz_cozumde_rozet_yok() -> None:
    _, bulgu, svg = _cift("H0")
    assert bulgu.is_clean
    for metin in viz.EKSIK_METNI.values():
        assert metin not in svg


def test_rozet_adim_kutusuyla_cakismaz() -> None:
    """Rozet kutunun SAGINDA durmali.

    Ustune konsaydi adimlar arasi bagimlilik okunu orterdi; sol panele
    konsaydi iki ucgenli sekillerin ustune binerdi.
    """
    import re

    for sinif in ("H1", "H2", "H3"):
        _, _, svg = _cift(sinif)
        # Adım kutuları rx="7", rozet rx="12" ile çizilir; ayrım buradan yapılır
        kutular = [
            float(m.group(1))
            for m in re.finditer(r'<rect x="([\d.]+)"[^>]*\srx="7"', svg)
        ]
        rozetler = [
            float(m.group(1))
            for m in re.finditer(r'<rect x="([\d.]+)"[^>]*\srx="12"', svg)
        ]
        assert kutular and rozetler, f"{sinif}: kutu veya rozet bulunamadi"
        assert min(rozetler) > max(kutular), f"{sinif}: rozet kutularin solunda"


def test_cift_graf_bos_adimda_patlamaz() -> None:
    svg = viz.dual_graph_svg({"points": [], "segments": []}, "<svg></svg>", [])
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_app_modulu_derlenir() -> None:
    """app.py sozdizimsel olarak gecerli mi? (Streamlit calistirmadan)"""
    import py_compile

    py_compile.compile(str(ROOT / "app.py"), doraise=True)
