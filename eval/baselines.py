"""Taban çizgileri — metrikler bunlar olmadan yorumlanamaz.

Çözümler 2–5 adımdan oluştuğu için, hatalı adımı **rastgele tahmin eden** bir
sistem M3'te %25–50 arası bir skor alır. Dolayısıyla "model hatayı %45
doğrulukla yerelleştirdi" cümlesi tek başına hiçbir şey ifade etmez — rastgeleden
daha kötü bile olabilir.

Üç taban çizgisi hesaplanır:

    rastgele        : sınıfı ve adımı düzgün dağılımdan seç
    cogunluk        : her zaman en sık görülen sınıfı söyle
    hep_ilk_adim    : hata her zaman ilk adımdadır de

Üçüncüsü özellikle önemlidir. Üreteç, hatalı adımın konumunu dolaştırmakla
yükümlüdür (docs/taksonomi.md §7); bu taban çizgisi yüksek çıkarsa dolaştırma
işlememiş demektir ve M3 anlamını yitirir.

Skorlar veri kümesinin kendisinden hesaplanır, formülle varsayılmaz.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

CLASSES = ("H0", "H1", "H2", "H3")

#: Rastgele taban çizgisi kaç kez örneklenerek ortalanacak.
DENEME = 200
TOHUM = 20260909


@dataclass(frozen=True)
class Baseline:
    ad: str
    m1_f1: float
    m2_dogruluk: float
    m3_dogruluk: float
    aciklama: str = ""


def _f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    kesinlik = tp / (tp + fp)
    duyarlilik = tp / (tp + fn)
    return 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)


def _m1_f1(gercek: Sequence[str], tahmin: Sequence[str]) -> float:
    """Pozitif sınıf = 'hata var'."""
    tp = sum(1 for g, t in zip(gercek, tahmin) if g != "H0" and t != "H0")
    fp = sum(1 for g, t in zip(gercek, tahmin) if g == "H0" and t != "H0")
    fn = sum(1 for g, t in zip(gercek, tahmin) if g != "H0" and t == "H0")
    return _f1(tp, fp, fn)


def _step_ids(solution: dict[str, Any]) -> list[str]:
    return [s["id"] for s in solution["steps"]]


def compute(
    solutions: Sequence[dict[str, Any]],
    labels: Sequence[dict[str, Any]],
) -> list[Baseline]:
    """Verilen küme için üç taban çizgisini hesaplar."""
    if not solutions:
        return []

    gercek_sinif = [lab["error_class"] for lab in labels]
    gercek_adim = [lab.get("error_step") for lab in labels]

    # Hata içeren örnekler: M3 yalnızca bunlar üzerinde tanımlıdır
    hatali = [i for i, s in enumerate(gercek_sinif) if s != "H0"]

    rng = random.Random(TOHUM)

    # --- rastgele -------------------------------------------------------
    m1_toplam = m2_toplam = m3_toplam = 0.0
    for _ in range(DENEME):
        tahmin = [rng.choice(CLASSES) for _ in solutions]
        m1_toplam += _m1_f1(gercek_sinif, tahmin)
        m2_toplam += sum(1 for g, t in zip(gercek_sinif, tahmin) if g == t) / len(solutions)

        if hatali:
            isabet = sum(
                1
                for i in hatali
                if rng.choice(_step_ids(solutions[i])) == gercek_adim[i]
            )
            m3_toplam += isabet / len(hatali)

    rastgele = Baseline(
        "rastgele",
        m1_toplam / DENEME,
        m2_toplam / DENEME,
        m3_toplam / DENEME if hatali else float("nan"),
        f"{DENEME} cekilisin ortalamasi",
    )

    # --- cogunluk sinifi ------------------------------------------------
    en_sik = Counter(gercek_sinif).most_common(1)[0][0]
    sabit = [en_sik] * len(solutions)
    cogunluk = Baseline(
        "cogunluk",
        _m1_f1(gercek_sinif, sabit),
        sum(1 for g in gercek_sinif if g == en_sik) / len(solutions),
        0.0 if hatali else float("nan"),
        f"her zaman '{en_sik}'",
    )

    # --- hep ilk adim ---------------------------------------------------
    if hatali:
        ilk_isabet = sum(
            1 for i in hatali if _step_ids(solutions[i])[0] == gercek_adim[i]
        ) / len(hatali)
    else:
        ilk_isabet = float("nan")

    hep_ilk = Baseline(
        "hep_ilk_adim",
        float("nan"),
        float("nan"),
        ilk_isabet,
        "hata her zaman ilk adimdadir varsayimi",
    )

    return [rastgele, cogunluk, hep_ilk]


def step_position_distribution(
    solutions: Sequence[dict[str, Any]], labels: Sequence[dict[str, Any]]
) -> Counter[int]:
    """Hatalı adımın kaçıncı sırada olduğunun dağılımı (1 tabanlı)."""
    dagilim: Counter[int] = Counter()
    for sol, lab in zip(solutions, labels):
        adim = lab.get("error_step")
        if adim:
            ids = _step_ids(sol)
            if adim in ids:
                dagilim[ids.index(adim) + 1] += 1
    return dagilim


def as_markdown(baselines: Sequence[Baseline]) -> str:
    def g(x: float) -> str:
        return "—" if x != x else f"{x:.3f}"  # NaN kontrolu

    satirlar = [
        "| Taban çizgisi | M1 · F1 | M2 · Doğruluk | M3 · Doğruluk | Not |",
        "|---|---|---|---|---|",
    ]
    for b in baselines:
        satirlar.append(
            f"| {b.ad} | {g(b.m1_f1)} | {g(b.m2_dogruluk)} | {g(b.m3_dogruluk)} | {b.aciklama} |"
        )
    return "\n".join(satirlar)
