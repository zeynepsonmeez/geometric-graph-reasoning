"""Değerlendirme boru hattının denetimi: taban çizgileri ve metrikler."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

import baselines  # noqa: E402
import generator as gen  # noqa: E402
import llm_checker as llm  # noqa: E402
import run_experiment as rx  # noqa: E402

SOLUTIONS = gen.generate(total=400, seed=20260906)
LABELS = [s["label"] for s in SOLUTIONS]

#: M3'un ayirt edici olabilmesi icin taban cizgilerinin dusuk kalmasi gerekir.
#: Bu esikler olcumden cikmistir; asilirlarsa uretecin zincir uzatmasi bozulmustur.
RASTGELE_M3_TAVAN = 0.40
ILK_ADIM_M3_TAVAN = 0.50


# --------------------------------------------------------------------------
# Taban çizgileri — M3'ün anlamlılığını koruyan testler
# --------------------------------------------------------------------------


def _by_name(bs: list[baselines.Baseline]) -> dict[str, baselines.Baseline]:
    return {b.ad: b for b in bs}


def test_rastgele_m3_yeterince_dusuk() -> None:
    """Tek adimli cozumlerde rastgele tahmin HER ZAMAN dogrudur.

    Bu esik asilirsa zincir yeterince uzun degil demektir ve M3 olcemez.
    """
    b = _by_name(baselines.compute(SOLUTIONS, LABELS))["rastgele"]
    assert b.m3_dogruluk < RASTGELE_M3_TAVAN, (
        f"rastgele M3 = {b.m3_dogruluk:.3f}. Cozum zincirleri kisalmis; "
        f"src/generator.py MIN_HATALI_ADIM degerine bakin."
    )


def test_hep_ilk_adim_yeterince_dusuk() -> None:
    """Hata hep basta olsaydi model 'ilk adimi soyle' diyerek yuksek skor alirdi."""
    b = _by_name(baselines.compute(SOLUTIONS, LABELS))["hep_ilk_adim"]
    assert b.m3_dogruluk < ILK_ADIM_M3_TAVAN, f"hep_ilk_adim M3 = {b.m3_dogruluk:.3f}"


def test_hatali_cozumler_yeterince_uzun() -> None:
    hatali = [s for s in SOLUTIONS if s["label"]["error_class"] != "H0"]
    kisa = [s["problem_id"] for s in hatali if len(s["steps"]) < gen.MIN_HATALI_ADIM]
    assert not kisa, f"{len(kisa)} hatali cozum {gen.MIN_HATALI_ADIM} adimdan kisa"


def test_konum_dagilimi_tek_noktada_toplanmamis() -> None:
    d = baselines.step_position_distribution(SOLUTIONS, LABELS)
    toplam = sum(d.values())
    assert len(d) >= 3, f"hata yalnizca {len(d)} farkli konumda: {dict(d)}"
    assert max(d.values()) / toplam < 0.5, f"tek konumda yigilma: {dict(d)}"


def test_cogunluk_m1_yuksek_cikar() -> None:
    """M1'in kolay oldugunu gosterir: ornekler cogunlukla hatali oldugu icin
    'her zaman hata var' demek bile yuksek F1 verir. M1 tek basina yorumlanamaz."""
    b = _by_name(baselines.compute(SOLUTIONS, LABELS))["cogunluk"]
    assert b.m1_f1 > 0.7


def test_bos_kumede_taban_cizgisi_patlamaz() -> None:
    assert baselines.compute([], []) == []


def test_markdown_uretilir() -> None:
    md = baselines.as_markdown(baselines.compute(SOLUTIONS[:50], LABELS[:50]))
    assert "rastgele" in md and "hep_ilk_adim" in md


# --------------------------------------------------------------------------
# Metrikler
# --------------------------------------------------------------------------


def _pred(sinif: str, adim: str | None) -> llm.Prediction:
    return llm.Prediction(
        hata_var_mi=sinif != "H0", hata_sinifi=sinif, hatali_adim=adim, aciklama=""
    )


def _sol(pid: str, n_steps: int = 3) -> dict:
    return {
        "problem_id": pid,
        "steps": [{"id": f"s{i+1}"} for i in range(n_steps)],
    }


def test_mukemmel_tahmin_tam_puan() -> None:
    gercek = [{"error_class": "H1", "error_step": "s2"}, {"error_class": "H0", "error_step": None}]
    tahmin = [_pred("H1", "s2"), _pred("H0", None)]
    m = rx.score(gercek, tahmin, [_sol("a"), _sol("b")])

    assert m.m1_f1 == pytest.approx(1.0)
    assert m.m2_dogruluk == pytest.approx(1.0)
    assert m.m3_dogruluk == pytest.approx(1.0)
    assert m.yanlis_pozitif_orani == pytest.approx(0.0)


def test_sinif_dogru_adim_yanlis_m3_dusurur() -> None:
    """Projenin beklenen bulgusu: model turu bulur, yeri sasirir."""
    gercek = [{"error_class": "H1", "error_step": "s2"}]
    tahmin = [_pred("H1", "s1")]
    m = rx.score(gercek, tahmin, [_sol("a")])

    assert m.m2_dogruluk == pytest.approx(1.0)
    assert m.m3_dogruluk == pytest.approx(0.0)


def test_yanlis_pozitif_orani_h0_uzerinden() -> None:
    gercek = [{"error_class": "H0", "error_step": None}] * 4
    tahmin = [_pred("H2", "s1"), _pred("H0", None), _pred("H0", None), _pred("H0", None)]
    m = rx.score(gercek, tahmin, [_sol(f"s{i}") for i in range(4)])
    assert m.yanlis_pozitif_orani == pytest.approx(0.25)


def test_gecersiz_yanit_metrige_karismaz() -> None:
    """Basarisiz API cagrisi, yanlis tahmin gibi puanlanmamali."""
    gercek = [{"error_class": "H1", "error_step": "s1"}, {"error_class": "H1", "error_step": "s1"}]
    tahmin = [_pred("H1", "s1"), llm.Prediction(error="ag hatasi")]
    m = rx.score(gercek, tahmin, [_sol("a"), _sol("b")])

    assert m.n == 1 and m.gecersiz == 1
    assert m.m2_dogruluk == pytest.approx(1.0)


def test_m3_yalnizca_hatali_orneklerde_tanimli() -> None:
    gercek = [{"error_class": "H0", "error_step": None}] * 3
    tahmin = [_pred("H0", None)] * 3
    m = rx.score(gercek, tahmin, [_sol(f"s{i}") for i in range(3)])
    assert m.m3_dogruluk != m.m3_dogruluk  # NaN: hesaplanacak ornek yok


def test_tum_yanitlar_gecersizse_patlamaz() -> None:
    gercek = [{"error_class": "H1", "error_step": "s1"}]
    m = rx.score(gercek, [llm.Prediction(error="x")], [_sol("a")])
    assert m.n == 0 and m.gecersiz == 1


# --------------------------------------------------------------------------
# Uçtan uca (çevrimdışı)
# --------------------------------------------------------------------------


def test_kararlilik_ayni_yanitta_bir() -> None:
    t = [[_pred("H1", "s1")], [_pred("H1", "s1")]]
    assert rx.stability(t) == pytest.approx(1.0)


def test_kararlilik_farkli_yanitta_sifir() -> None:
    t = [[_pred("H1", "s1")], [_pred("H2", "s1")]]
    assert rx.stability(t) == pytest.approx(0.0)


def test_rapor_uretilir() -> None:
    ds = rx.Dataset("deneme", SOLUTIONS[:20], LABELS[:20])
    client = llm.FakeClient()
    tekrarlar = rx.run_arm(ds, "K2", client, repeats=1, model="test", use_cache=False)

    sonuclar = {
        ds.ad: {
            "n": len(ds),
            "baselines": baselines.as_markdown(baselines.compute(ds.solutions, ds.labels)),
            "konum_dagilimi": dict(baselines.step_position_distribution(ds.solutions, ds.labels)),
            "arms": {
                "K2": {
                    "metrics": rx.score(ds.labels, tekrarlar[0], ds.solutions),
                    "confusion": rx.confusion(ds.labels, tekrarlar[0]),
                    "kararlilik": rx.stability(tekrarlar),
                }
            },
        }
    }
    rapor = rx.build_report(sonuclar, "test-model", 1)

    assert "Deney Sonuçları" in rapor
    assert "Taban çizgileri" in rapor
    assert "Karışıklık matrisi" in rapor


def test_bos_elle_yazilan_kume_none_dondurur() -> None:
    assert rx.verifier_vs_human(rx.Dataset("bos", [], [])) is None
