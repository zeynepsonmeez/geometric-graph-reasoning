"""Sembolik doğrulayıcının denetimi.

İki ayrı denetim türü içerir ve ayrımı korumak önemlidir:

1. **Elle yazılmış birim vakalar** (§ Birim vakalar) — üreteçten HİÇ geçmeyen,
   bu dosyada doğrudan kurulmuş şekiller. Doğrulayıcının gerçek sınavı budur:
   üretecin ürettiği kalıpları değil, taksonomi kurallarını uyguluyor mu?

2. **Üreteçle uyum** (§ Uyum) — sentetik derlem üzerinde etiketlerle örtüşme.
   Bu bir BAŞARIM ÖLÇÜSÜ DEĞİLDİR. Doğrulayıcı oracle olduğu için sentetik
   veride yüksek skor alması beklenen davranıştır (docs/taksonomi.md §7).
   Test yalnızca regresyon koruması sağlar.

3. **Mutasyon denemesi** (§ Mutasyon) — geçerli bir çözümden verilen silinince
   doğrulayıcı bunu yakalıyor mu? Üretecin kurmadığı bir hatayı yakalaması,
   kural setini gerçekten uyguladığının kanıtıdır.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import generator as gen  # noqa: E402
import verifier as vf  # noqa: E402


# --------------------------------------------------------------------------
# Elle yazılmış birim vakalar
# --------------------------------------------------------------------------


def _figure(**over):
    base = {
        "points": ["A", "B", "C"],
        "segments": [
            {"from": "A", "to": "B", "type": "side", "length": 5},
            {"from": "B", "to": "C", "type": "side", "length": 7},
            {"from": "A", "to": "C", "type": "side", "length": None},
        ],
        "angles": [],
        "perpendicular": [],
        "congruent_segments": [],
        "similar": [],
    }
    base.update(over)
    return base


def test_h0_diklik_verilmisse_pisagor_gecerli() -> None:
    f = _figure(perpendicular=["B"])
    steps = [{"id": "s1", "claim": "|AC|² = 5² + 7²", "rule": "pisagor",
              "depends_on": [], "refs": {"vertex": "B"}}]
    assert vf.verify(f, steps).is_clean


def test_h1_diklik_verilmeden_verilen_denirse() -> None:
    """Kapalı dünya: listede olmayanı 'verilen' saymak H1'dir."""
    f = _figure(perpendicular=[])
    steps = [
        {"id": "s1", "claim": "m(B) = 90", "rule": "verilen",
         "depends_on": [], "refs": {"asserts": "perpendicular", "vertex": "B"}},
        {"id": "s2", "claim": "|AC|² = 5² + 7²", "rule": "pisagor",
         "depends_on": ["s1"], "refs": {"vertex": "B"}},
    ]
    f_ = vf.verify(f, steps)
    assert f_.error_class == "H1"
    assert f_.error_step == "s1", "hata, teoremin uygulandigi adimda degil iddiada"


def test_h3_diklik_hic_anilmadan_pisagor() -> None:
    """H1'den farkı: 'verilen' iddiası YOK, koşul hiç denetlenmemiş (§4.2)."""
    f = _figure(perpendicular=[])
    steps = [{"id": "s1", "claim": "|AC|² = 5² + 7²", "rule": "pisagor",
              "depends_on": [], "refs": {"vertex": "B"}}]
    f_ = vf.verify(f, steps)
    assert f_.error_class == "H3"
    assert f_.error_step == "s1"


def test_h1_ve_h3_ayni_figurde_farkli_teshis() -> None:
    """Aynı eksik verilen, iki farklı sınıf üretir. Ayrım 'verilen' iddiasındadır."""
    f = _figure(perpendicular=[])
    ortak = {"id": "sX", "claim": "|AC|² = 5² + 7²", "rule": "pisagor",
             "depends_on": [], "refs": {"vertex": "B"}}

    h3 = vf.verify(f, [dict(ortak, id="s1")])
    h1 = vf.verify(f, [
        {"id": "s1", "claim": "m(B) = 90", "rule": "verilen", "depends_on": [],
         "refs": {"asserts": "perpendicular", "vertex": "B"}},
        dict(ortak, id="s2", depends_on=["s1"]),
    ])
    assert (h3.error_class, h1.error_class) == ("H3", "H1")


def test_h2_yukseklik_kenarortay_karistirmasi() -> None:
    f = _figure(
        points=["A", "B", "C", "H"],
        segments=[
            {"from": "B", "to": "C", "type": "side", "length": 12},
            {"from": "A", "to": "B", "type": "side", "length": None},
            {"from": "A", "to": "C", "type": "side", "length": None},
            {"from": "A", "to": "H", "type": "altitude", "length": None},
        ],
    )
    steps = [{"id": "s1", "claim": "|BH| = |HC| = 6", "rule": "kenarortay",
              "depends_on": [], "refs": {"segment": "AH"}}]
    f_ = vf.verify(f, steps)
    assert f_.error_class == "H2"
    assert f_.violated == "segment_type"


def test_h0_dogru_tipte_eleman_kullanilirsa_temiz() -> None:
    f = _figure(
        points=["A", "B", "C", "M"],
        segments=[
            {"from": "B", "to": "C", "type": "side", "length": 12},
            {"from": "A", "to": "B", "type": "side", "length": None},
            {"from": "A", "to": "C", "type": "side", "length": None},
            {"from": "A", "to": "M", "type": "median", "length": None},
        ],
    )
    steps = [{"id": "s1", "claim": "|BM| = |MC| = 6", "rule": "kenarortay",
              "depends_on": [], "refs": {"segment": "AM"}}]
    assert vf.verify(f, steps).is_clean


def test_h3_dis_aci_yanlis_cift() -> None:
    """Dış açı, kendisine KOMŞU OLMAYAN iki iç açının toplamıdır."""
    f = _figure(angles=[{"vertex": "A", "value": 50}, {"vertex": "B", "value": 60},
                        {"vertex": "C", "value": None}])
    dogru = [{"id": "s1", "claim": "dış(C) = 50 + 60", "rule": "dis_aci",
              "depends_on": [], "refs": {"exterior": "C", "remote": ["A", "B"]}}]
    yanlis = [{"id": "s1", "claim": "dış(C) = 50 + 70", "rule": "dis_aci",
               "depends_on": [], "refs": {"exterior": "C", "remote": ["A", "C"]}}]

    assert vf.verify(f, dogru).is_clean
    assert vf.verify(f, yanlis).error_class == "H3"


def test_h2_benzerlikte_yanlis_kenar_eslestirmesi() -> None:
    """ABC ~ DEF ise A↔D, B↔E, C↔F. Eşleme bu sırayı izlemelidir."""
    f = _figure(
        points=["A", "B", "C", "D", "E", "F"],
        segments=[
            {"from": "A", "to": "B", "type": "side", "length": 4},
            {"from": "B", "to": "C", "type": "side", "length": 6},
            {"from": "A", "to": "C", "type": "side", "length": None},
            {"from": "D", "to": "E", "type": "side", "length": None},
            {"from": "E", "to": "F", "type": "side", "length": None},
            {"from": "D", "to": "F", "type": "side", "length": None},
        ],
        similar=[["ABC", "DEF"]],
    )
    dogru = [{"id": "s1", "claim": "|DE| = 2·|AB|", "rule": "benzerlik_orani",
              "depends_on": [], "refs": {"maps": [["AB", "DE"]]}}]
    yanlis = [{"id": "s1", "claim": "|DE| = 2·|BC|", "rule": "benzerlik_orani",
               "depends_on": [], "refs": {"maps": [["BC", "DE"]]}}]

    assert vf.verify(f, dogru).is_clean
    f_ = vf.verify(f, yanlis)
    assert f_.error_class == "H2"
    assert f_.violated == "correspondence"


def test_ikizkenar_verilmemisse_taban_acilari_h3() -> None:
    f = _figure(congruent_segments=[])
    steps = [{"id": "s1", "claim": "m(B) = m(C)", "rule": "ikizkenar_taban",
              "depends_on": [], "refs": {}}]
    assert vf.verify(f, steps).error_class == "H3"


def test_ilk_hatada_durur() -> None:
    """Kirlenmiş sonraki adımlar ayrıca hata sayılmaz (§4.1)."""
    f = _figure(perpendicular=[], congruent_segments=[])
    steps = [
        {"id": "s1", "claim": "m(B) = m(C)", "rule": "ikizkenar_taban",
         "depends_on": [], "refs": {}},
        {"id": "s2", "claim": "|AC|² = 5² + 7²", "rule": "pisagor",
         "depends_on": ["s1"], "refs": {"vertex": "B"}},
    ]
    assert vf.verify(f, steps).error_step == "s1"


def test_taninmayan_kural_sessizce_gecmez() -> None:
    f = _figure(perpendicular=["B"])
    steps = [{"id": "s1", "claim": "?", "rule": "olmayan_teorem", "depends_on": []}]
    assert not vf.verify(f, steps).is_clean


def test_verify_imzasi_rendering_almaz() -> None:
    """Çizim bağlayıcı değildir: koordinatlar imzaya hiç girmez."""
    import inspect

    params = list(inspect.signature(vf.verify).parameters)
    assert params == ["figure", "steps"], f"beklenmeyen imza: {params}"


# --------------------------------------------------------------------------
# Mutasyon denemesi
# --------------------------------------------------------------------------


def test_gecerli_cozumden_verilen_silinince_yakalanir() -> None:
    """Üretecin KURMADIĞI bir hatayı doğrulayıcı yakalıyor mu?

    H0 örneklerinden verilenleri tek tek silip, çözümün artık geçersiz sayılması
    gerektiğini denetler. Bu, doğrulayıcının üretecin kalıplarını taklit etmek
    yerine kural setini uyguladığının kanıtıdır.
    """
    sols = [s for s in gen.generate(total=120, seed=4242)
            if s["label"]["error_class"] == "H0"]
    assert sols, "H0 ornegi uretilmedi"

    denenen = yakalanan = 0
    for s in sols:
        for alan in ("perpendicular", "congruent_segments", "similar"):
            if not s["figure"].get(alan):
                continue
            bozuk = copy.deepcopy(s["figure"])
            bozuk[alan] = []
            denenen += 1
            if not vf.verify(bozuk, s["steps"]).is_clean:
                yakalanan += 1

    assert denenen > 0, "silinebilecek verilen bulunamadi"
    assert yakalanan == denenen, (
        f"{denenen} mutasyondan yalnizca {yakalanan} tanesi yakalandi; "
        f"dogrulayici verilenleri gercekten denetlemiyor"
    )


def test_gecerli_cozumde_eleman_tipi_degisince_h2() -> None:
    """Yardımcı eleman tipi değiştirilince tanım karıştırma doğmalı."""
    sols = [s for s in gen.generate(total=200, seed=777)
            if s["label"]["error_class"] == "H0"]

    denenen = yakalanan = 0
    for s in sols:
        yardimci = [i for i, seg in enumerate(s["figure"]["segments"])
                    if seg["type"] in ("altitude", "median", "bisector")]
        if not yardimci:
            continue
        bozuk = copy.deepcopy(s["figure"])
        i = yardimci[0]
        mevcut = bozuk["segments"][i]["type"]
        bozuk["segments"][i]["type"] = "median" if mevcut != "median" else "altitude"
        denenen += 1
        if vf.verify(bozuk, s["steps"]).error_class == "H2":
            yakalanan += 1

    assert denenen > 0, "yardimci eleman iceren H0 ornegi yok"
    assert yakalanan == denenen, f"{denenen} tip degisiminden {yakalanan} yakalandi"


# --------------------------------------------------------------------------
# Üreteçle uyum — başarım ölçüsü DEĞİL, regresyon koruması
# --------------------------------------------------------------------------


def test_sentetik_derlemle_tam_uyum() -> None:
    """Oracle, kendi spesifikasyonundan üretilmiş veriyle örtüşmelidir.

    DİKKAT: Bu bir başarım sonucu değildir ve bildiride böyle raporlanmaz.
    Doğrulayıcı altın standarttır; sentetik veride %100 alması tanım gereğidir.
    Buradaki işlevi yalnızca regresyon yakalamaktır.
    """
    sols = gen.generate(total=400, seed=20260906)
    uyusmaz = [
        (s["problem_id"], s["label"]["error_class"], vf.verify_solution(s).error_class)
        for s in sols
        if vf.verify_solution(s).error_class != s["label"]["error_class"]
    ]
    assert not uyusmaz, f"{len(uyusmaz)} uyusmazlik, ilk 5: {uyusmaz[:5]}"


def test_hatali_adim_da_ortusur() -> None:
    sols = gen.generate(total=400, seed=20260906)
    uyusmaz = [
        s["problem_id"] for s in sols
        if vf.verify_solution(s).error_step != s["label"]["error_step"]
    ]
    assert not uyusmaz, f"{len(uyusmaz)} adim uyusmazligi, ilk 5: {uyusmaz[:5]}"
