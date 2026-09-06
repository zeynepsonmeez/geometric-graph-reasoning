"""Sentetik üretecin ve çizim motorunun denetimi."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import generator as gen  # noqa: E402
import renderer  # noqa: E402

SOLUTION_SCHEMA = json.loads(
    (ROOT / "schema" / "solution.schema.json").read_text(encoding="utf-8")
)

TOTAL = 200
SOLUTIONS = gen.generate(total=TOTAL, seed=1234)


# --------------------------------------------------------------------------
# Şema ve temel bütünlük
# --------------------------------------------------------------------------


def test_istenen_sayida_uretilir() -> None:
    assert len(SOLUTIONS) == TOTAL


def test_hepsi_semaya_uygun() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    for s in SOLUTIONS:
        jsonschema.validate(s, SOLUTION_SCHEMA)


def test_siniflar_dengeli() -> None:
    sayilar = Counter(s["label"]["error_class"] for s in SOLUTIONS)
    assert set(sayilar) == {"H0", "H1", "H2", "H3"}
    assert len(set(sayilar.values())) == 1, f"dengesiz dagilim: {dict(sayilar)}"


def test_noktalar_ayrik() -> None:
    """Aynı şekilde iki nokta aynı adı taşıyamaz (P6'da iki ayrı üçgen var)."""
    for s in SOLUTIONS:
        noktalar = s["figure"]["points"]
        assert len(noktalar) == len(set(noktalar)), f"{s['problem_id']}: yinelenen nokta adi"


def test_uretilmis_deger_kalmadi() -> None:
    """Hiçbir alanda yerine konmamış {yer_tutucu} kalmamalı."""
    kalinti = re.compile(r"\{[A-Za-z][A-Za-z0-9_]*\}")
    for s in SOLUTIONS:
        bulunan = kalinti.findall(json.dumps(s, ensure_ascii=False))
        assert not bulunan, f"{s['problem_id']}: yerine konmamis yer tutucu {bulunan}"


def test_ayni_tohum_ayni_sonuc() -> None:
    """Deneyin tekrarlanabilir olması için üretim deterministik olmalı."""
    a = gen.generate(total=40, seed=99)
    b = gen.generate(total=40, seed=99)
    assert a == b


# --------------------------------------------------------------------------
# Etiket tutarlılığı (docs/taksonomi.md §4)
# --------------------------------------------------------------------------


def test_h0_hatali_adim_tasimaz() -> None:
    for s in SOLUTIONS:
        if s["label"]["error_class"] == "H0":
            assert s["label"]["error_step"] is None, s["problem_id"]


def test_hata_adimi_gercekten_var() -> None:
    for s in SOLUTIONS:
        adim = s["label"]["error_step"]
        if adim is None:
            continue
        ids = [x["id"] for x in s["steps"]]
        assert adim in ids, f"{s['problem_id']}: '{adim}' adimlar arasinda yok ({ids})"


def test_bagimliliklar_geriye_donuk() -> None:
    """depends_on yalnızca kendinden önceki adımlara işaret edebilir (DAG)."""
    for s in SOLUTIONS:
        gorulen: set[str] = set()
        for step in s["steps"]:
            for dep in step["depends_on"]:
                assert dep in gorulen, f"{s['problem_id']}/{step['id']}: ileri bagimlilik"
            gorulen.add(step["id"])


def test_h1_verilen_iddiasi_icerir() -> None:
    """H1 ile H3 ayrımı 'verilen' iddiasının varlığına dayanır (§4.2)."""
    for s in SOLUTIONS:
        if s["label"]["error_class"] != "H1":
            continue
        hatali = next(x for x in s["steps"] if x["id"] == s["label"]["error_step"])
        assert hatali["rule"] == "verilen", (
            f"{s['problem_id']}: H1'in hatali adimi 'verilen' olmali, "
            f"'{hatali['rule']}' bulundu"
        )


# --------------------------------------------------------------------------
# Şablon izi (docs/taksonomi.md §7)
# --------------------------------------------------------------------------


def test_hata_konumu_dagilmis() -> None:
    """Hata hep ilk adımda olamaz.

    Aksi hâlde model "ilk adimi soyle" diyerek yuksek M3 skoru alir ve
    yerellestirme metrigi anlamsizlasir.
    """
    konumlar = Counter()
    for s in SOLUTIONS:
        adim = s["label"]["error_step"]
        if adim:
            konumlar[[x["id"] for x in s["steps"]].index(adim) + 1] += 1

    assert len(konumlar) >= 2, f"hata hep ayni konumda: {dict(konumlar)}"
    en_sik = max(konumlar.values()) / sum(konumlar.values())
    assert en_sik < 0.75, f"hatalarin %{en_sik:.0%}'i tek konumda: {dict(konumlar)}"


def test_kose_adlari_cesitli() -> None:
    ilk_koseler = Counter(s["figure"]["points"][0] for s in SOLUTIONS)
    assert len(ilk_koseler) >= 4, f"kose adlari yeterince cesitli degil: {dict(ilk_koseler)}"


def test_her_hata_sinifi_en_az_iki_aileden() -> None:
    aileler: dict[str, set[str]] = {}
    for s in SOLUTIONS:
        sinif = s["label"]["error_class"]
        if sinif != "H0":
            aileler.setdefault(sinif, set()).add(s["family"])
    for sinif in ("H1", "H2", "H3"):
        assert len(aileler.get(sinif, set())) >= 2, (
            f"{sinif} yalnizca {sorted(aileler.get(sinif, set()))} ailesinden geliyor"
        )


# --------------------------------------------------------------------------
# Çizim motoru
# --------------------------------------------------------------------------


def _triangle_vertices(figure: dict) -> list[str]:
    return renderer._find_triangles(
        list(figure["points"]), figure["segments"]
    )[0]


def test_verilen_diklik_dik_cizilir() -> None:
    """docs/taksonomi.md §1: verilen nitel iliskiler birebir dogru cizilir.

    Verilmis bir dik acinin dik cizilmemesi, cizimin verilenle CELISMESI demektir;
    bu "temsili sekil" degil, hatadir.
    """
    denetlenen = 0
    for s in SOLUTIONS:
        perpendicular = s["figure"]["perpendicular"]
        if not perpendicular:
            continue
        kose = perpendicular[0]
        c = s["rendering"]["coords"]
        komsular = [p for p in _triangle_vertices(s["figure"]) if p != kose]
        if len(komsular) < 2:
            continue
        aci = renderer._angle_at(
            tuple(c[kose]), tuple(c[komsular[0]]), tuple(c[komsular[1]])
        )
        assert abs(aci - 90) < 0.5, f"{s['problem_id']}: verilen dik aci {aci:.1f} cizilmis"
        denetlenen += 1

    assert denetlenen > 0, "verilen diklik iceren hic ornek yok"


def test_misleading_h1_dikligi_verilmeden_dik_gosterir() -> None:
    """H1'in tuzagi: cizim dik gosterir ama figure.perpendicular BOSTUR."""
    bulundu = 0
    for s in SOLUTIONS:
        if s["label"]["error_class"] != "H1" or s["rendering"]["bias"] != "misleading":
            continue
        hatali = next(x for x in s["steps"] if x["id"] == s["label"]["error_step"])
        if "90" not in hatali["claim"]:
            continue

        assert not s["figure"]["perpendicular"], (
            f"{s['problem_id']}: diklik verilmis, o hâlde bu H1 degil"
        )
        c = s["rendering"]["coords"]
        koseler = _triangle_vertices(s["figure"])
        acilar = [
            renderer._angle_at(
                tuple(c[v]), *[tuple(c[o]) for o in koseler if o != v]
            )
            for v in koseler
        ]
        assert any(abs(a - 90) < 0.5 for a in acilar), (
            f"{s['problem_id']}: misleading cizim dik gostermiyor, tuzak yok"
        )
        bulundu += 1

    assert bulundu > 0, "dik aci tuzagi iceren hic H1 ornegi uretilmedi"


def test_svg_uretiliyor() -> None:
    for s in SOLUTIONS[:20]:
        svg = renderer.to_svg(s["figure"], s["rendering"]["coords"], s["rendering"]["note"])
        assert svg.startswith("<svg") and svg.endswith("</svg>")
        for nokta in s["figure"]["points"]:
            assert f">{nokta}<" in svg, f"{s['problem_id']}: {nokta} cizimde yok"


def test_verilen_uzunluklar_olcekli_cizilmez() -> None:
    """Sekil olcekli DEGILDIR: etiketlenen uzunluk oranlari cizime yansimaz.

    Bu testin gecmesi, cizimin dogru olmadigini degil, KASITLI olarak temsili
    oldugunu dogrular (docs/taksonomi.md §1).
    """
    olcekli = 0
    toplam = 0
    for s in SOLUTIONS:
        c = s["rendering"]["coords"]
        verilen = [
            seg for seg in s["figure"]["segments"]
            if seg.get("length") is not None and seg["from"] in c and seg["to"] in c
        ]
        if len(verilen) < 2:
            continue
        toplam += 1
        a, b = verilen[0], verilen[1]
        oran_verilen = a["length"] / b["length"]
        oran_cizim = renderer._dist(tuple(c[a["from"]]), tuple(c[a["to"]])) / max(
            renderer._dist(tuple(c[b["from"]]), tuple(c[b["to"]])), 1e-6
        )
        if abs(oran_verilen - oran_cizim) < 0.05:
            olcekli += 1

    if toplam:
        assert olcekli / toplam < 0.5, (
            f"orneklerin cogu olcekli cizilmis ({olcekli}/{toplam}); "
            f"temsili sekil olgusu kayboluyor"
        )
