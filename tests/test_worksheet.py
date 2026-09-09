"""Gönüllü föyünün denetimi.

Föy, körlük zincirinin son halkasıdır. Gönüllü hata sınıflarını görürse sınıfa
göre örnek üretmeye başlar ve elle yazılan küme, sentetik derlemin elle yazılmış
kopyasına dönüşür — kümenin tüm değeri bağımsızlığından gelir.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import renderer  # noqa: E402
import worksheet as ws  # noqa: E402

PROBLEMLER = ws.generate(30, seed=20260909)


# --------------------------------------------------------------------------
# Körlük
# --------------------------------------------------------------------------


def test_foy_hata_siniflarini_sizdirmaz() -> None:
    html = ws.to_html(PROBLEMLER)
    for sinif in ("H0", "H1", "H2", "H3"):
        assert sinif not in html, f"foyde {sinif} geciyor"


def test_foy_cozum_adimi_sizdirmaz() -> None:
    """Gonullu cozumu kendi yazmali; ornek cozum gormemeli.

    Dikkat: "kenarortay", "yukseklik" gibi kelimeler problem METNINDE dogal
    olarak gecer ("[CN] kenarortaydir") — bunlar verilendir, sizinti degildir.
    Gercek sizinti vektorleri kural KIMLIKLERI (alt cizgili, dogal metinde
    bulunmaz) ve adim yapisidir.
    """
    html = ws.to_html(PROBLEMLER)

    kural_kimlikleri = (
        "ic_acilar_toplami", "ikizkenar_taban", "hipotenus_kenarortay",
        "benzerlik_orani", "ucgen_esitsizligi", "dis_aci",
    )
    for kimlik in kural_kimlikleri:
        assert kimlik not in html, f"foyde kural kimligi '{kimlik}' geciyor"

    for yapi in ("gerekçe:", '"rule"', "depends_on", "refs"):
        assert yapi not in html, f"foyde adim yapisi '{yapi}' geciyor"

    # Adım kimlikleri (s1, s2, ...) föyde bulunmamalı
    import re

    assert not re.search(r"\bs[1-5]\b", html), "foyde adim kimligi geciyor"


def test_problem_nesnesi_cozum_tasimaz() -> None:
    assert not hasattr(ws.Problem, "steps")
    for p in PROBLEMLER:
        assert not hasattr(p, "steps") and not hasattr(p, "label")


def test_markdown_da_sizdirmaz() -> None:
    md = ws.to_markdown(PROBLEMLER)
    for sinif in ("H0", "H1", "H2", "H3"):
        assert sinif not in md


# --------------------------------------------------------------------------
# Kapsam
# --------------------------------------------------------------------------


def test_aileler_dengeli() -> None:
    dagilim = Counter(p.family for p in PROBLEMLER)
    assert set(dagilim) == set(ws.FAMILIES)
    assert max(dagilim.values()) - min(dagilim.values()) <= 1, dict(dagilim)


def test_yeterince_yaniltici_cizim_var() -> None:
    """Tuzakli sekil olmadan sekle guvenme hatasina zemin kalmaz."""
    oran = sum(1 for p in PROBLEMLER if p.bias == "misleading") / len(PROBLEMLER)
    assert oran >= 0.4, f"yaniltici cizim orani dusuk: {oran:.0%}"


def test_verileni_eksik_problemler_ipucu_tasir() -> None:
    """Cozulemeyen bir problemi notr cizimle vermek gonulluye kusurlu soru vermektir.

    Ders kitabinin bu durumda yaptigi sey sekli tuzakli cizmektir.
    """
    eksik = [p for p in PROBLEMLER if len(ws._verilen_satirlari(p.figure)) <= 1]
    assert eksik, "verileni az olan hic problem uretilmedi"
    for p in eksik:
        assert p.bias == "misleading", f"{p.etiket}: verileni eksik ama cizim notr"


def test_etiketler_benzersiz() -> None:
    etiketler = [p.etiket for p in PROBLEMLER]
    assert len(etiketler) == len(set(etiketler))


def test_her_problem_soru_ve_sekil_tasir() -> None:
    for p in PROBLEMLER:
        assert p.soru.strip()
        assert p.figure["points"]
        for nokta in p.figure["points"]:
            assert nokta in p.coords, f"{p.etiket}: {nokta} icin koordinat yok"


# --------------------------------------------------------------------------
# Çizim tutarlılığı
# --------------------------------------------------------------------------


def test_verilen_diklik_dik_cizilir() -> None:
    """bias serbestce secilse de VERILENLER baglayicidir."""
    denetlenen = 0
    for p in ws.generate(120, seed=3):
        per = p.figure.get("perpendicular") or []
        if not per:
            continue
        kose = per[0]
        ucgenler = renderer._find_triangles(list(p.figure["points"]), p.figure["segments"])
        if not ucgenler or kose not in p.coords:
            continue
        komsu = [x for x in ucgenler[0] if x != kose]
        if len(komsu) < 2:
            continue
        denetlenen += 1
        aci = renderer._angle_at(
            tuple(p.coords[kose]), tuple(p.coords[komsu[0]]), tuple(p.coords[komsu[1]])
        )
        assert abs(aci - 90) < 0.5, f"{p.etiket}: verilen dik aci {aci:.1f} cizilmis"

    assert denetlenen > 0


def test_ayni_tohum_ayni_foy() -> None:
    assert ws.generate(12, seed=42) == ws.generate(12, seed=42)


def test_auto_hint_serbest_nicelik_bulur() -> None:
    figure = {
        "points": ["A", "B", "C"],
        "segments": [
            {"from": "A", "to": "B", "type": "side", "length": 5},
            {"from": "B", "to": "C", "type": "side", "length": 7},
            {"from": "A", "to": "C", "type": "side", "length": None},
        ],
        "perpendicular": [],
        "congruent_segments": [],
    }
    ipucu = ws._auto_hint(figure)
    assert ipucu and ipucu["tip"] == "dik_aci"


def test_auto_hint_kisitli_sekilde_none_dondurur() -> None:
    figure = {
        "points": ["A", "B", "C"],
        "segments": [
            {"from": "A", "to": "B", "type": "side", "length": 5},
            {"from": "B", "to": "C", "type": "side", "length": 7},
            {"from": "A", "to": "C", "type": "side", "length": None},
        ],
        "perpendicular": ["B"],
        "congruent_segments": [["AB", "AC"]],
    }
    assert ws._auto_hint(figure) is None


def test_html_gecerli_svg_icerir() -> None:
    html = ws.to_html(PROBLEMLER[:3])
    assert html.count("<svg") == 3
    assert "Şekil ölçekli değildir" in html
