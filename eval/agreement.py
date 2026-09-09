"""Kodlayıcılar arası uyum: Cohen kappa ve uyuşmazlık raporu.

Sentetik derlemde etiket üreteçten gelir; kodlayıcı uyumu diye bir şey yoktur.
Bu ölçüm yalnızca **elle yazılan küme** için anlamlıdır ve taksonominin öznel
olmadığının kanıtıdır (docs/taksonomi.md §4.5).

Bildiriye girecek cümle şu biçimdedir:

    "İki bağımsız kodlayıcı arasında N örneklik kümede κ = 0.8X uyum elde edilmiştir."

κ > 0.75 iyi kabul edilir. Düşük çıkarsa bu bir başarısızlık DEĞİL, taksonominin
netleştirilmesi gerektiğinin sinyalidir ve o hâliyle raporlanır.

Kullanım:
    python eval/agreement.py            # raporu ekrana yazar
    python eval/agreement.py --write    # eval/agreement.md dosyasına da yazar
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import handwritten as hw  # noqa: E402

REPORT_PATH = ROOT / "eval" / "agreement.md"

#: κ yorumlama eşikleri (Landis & Koch ölçeği, yaygın kullanım).
KAPPA_LABELS = [
    (0.81, "neredeyse tam uyum"),
    (0.61, "önemli düzeyde uyum"),
    (0.41, "orta düzeyde uyum"),
    (0.21, "zayıf uyum"),
    (0.00, "çok zayıf uyum"),
]


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Cohen kappa. scikit-learn varsa onu kullanır, yoksa elle hesaplar."""
    try:
        from sklearn.metrics import cohen_kappa_score

        return float(cohen_kappa_score(a, b))
    except ImportError:
        pass

    n = len(a)
    if n == 0:
        return float("nan")

    gozlenen = sum(1 for x, y in zip(a, b) if x == y) / n
    sayim_a, sayim_b = Counter(a), Counter(b)
    beklenen = sum(sayim_a[k] * sayim_b[k] for k in set(a) | set(b)) / (n * n)

    if beklenen == 1.0:
        return 1.0
    return (gozlenen - beklenen) / (1 - beklenen)


def interpret(kappa: float) -> str:
    for esik, etiket in KAPPA_LABELS:
        if kappa >= esik:
            return etiket
    return "uyum yok"


def build_report() -> tuple[str, dict[str, object]]:
    a1 = hw.load_labels("A1")
    a2 = hw.load_labels("A2")
    ortak = sorted(set(a1) & set(a2))

    satirlar: list[str] = ["# Kodlayıcılar Arası Uyum", ""]

    if not ortak:
        satirlar += [
            "> Henüz karşılaştırılabilir etiket yok.",
            "",
            f"- `labels/A1.json`: {len(a1)} etiket",
            f"- `labels/A2.json`: {len(a2)} etiket",
            "",
            "Protokol için `data/handwritten/README.md` dosyasına bakın.",
        ]
        return "\n".join(satirlar) + "\n", {"n": 0}

    siniflar_a = [a1[p]["error_class"] for p in ortak]
    siniflar_b = [a2[p]["error_class"] for p in ortak]
    kappa = cohen_kappa(siniflar_a, siniflar_b)

    sinif_uyum = sum(1 for x, y in zip(siniflar_a, siniflar_b) if x == y)
    adim_uyum = sum(
        1 for p in ortak if a1[p].get("error_step") == a2[p].get("error_step")
    )

    satirlar += [
        f"Karşılaştırılan örnek sayısı: **{len(ortak)}**",
        "",
        "| Ölçüm | Değer |",
        "|---|---|",
        f"| Cohen κ (hata sınıfı) | **{kappa:.3f}** — {interpret(kappa)} |",
        f"| Ham sınıf uyumu | {sinif_uyum}/{len(ortak)} = {sinif_uyum / len(ortak):.1%} |",
        f"| Hatalı adım uyumu | {adim_uyum}/{len(ortak)} = {adim_uyum / len(ortak):.1%} |",
        "",
    ]

    if kappa < 0.75:
        satirlar += [
            "> **κ < 0.75.** Bu bir başarısızlık değildir; taksonominin",
            "> netleştirilmesi gerektiğinin sinyalidir. Aşağıdaki uyuşmazlıkları",
            "> inceleyip `docs/taksonomi.md` §4.4'teki karar kurallarını",
            "> keskinleştirin ve bu durumu bildiride raporlayın.",
            "",
        ]

    # Karışıklık matrisi
    siniflar = sorted(set(siniflar_a) | set(siniflar_b))
    matris = Counter(zip(siniflar_a, siniflar_b))
    satirlar += ["## Karışıklık matrisi (satır: A1, sütun: A2)", ""]
    satirlar.append("| A1 \\ A2 | " + " | ".join(siniflar) + " |")
    satirlar.append("|---" * (len(siniflar) + 1) + "|")
    for x in siniflar:
        hucreler = [str(matris.get((x, y), 0)) for y in siniflar]
        satirlar.append(f"| **{x}** | " + " | ".join(hucreler) + " |")
    satirlar.append("")

    # Uyuşmazlıklar
    farklar = [p for p in ortak if a1[p]["error_class"] != a2[p]["error_class"]]
    satirlar += [f"## Uyuşmazlıklar ({len(farklar)})", ""]
    if farklar:
        satirlar += ["| Örnek | A1 | A2 |", "|---|---|---|"]
        for p in farklar:
            satirlar.append(f"| `{p}` | {a1[p]['error_class']} | {a2[p]['error_class']} |")
    else:
        satirlar.append("Sınıf düzeyinde uyuşmazlık yok.")
    satirlar.append("")

    # Sınıf aynı ama adım farklı
    adim_farki = [
        p for p in ortak
        if a1[p]["error_class"] == a2[p]["error_class"]
        and a1[p].get("error_step") != a2[p].get("error_step")
    ]
    if adim_farki:
        satirlar += [
            f"## Sınıf aynı, hatalı adım farklı ({len(adim_farki)})",
            "",
            "| Örnek | Sınıf | A1 adım | A2 adım |",
            "|---|---|---|---|",
        ]
        for p in adim_farki:
            satirlar.append(
                f"| `{p}` | {a1[p]['error_class']} | "
                f"{a1[p].get('error_step')} | {a2[p].get('error_step')} |"
            )
        satirlar.append("")

    return "\n".join(satirlar) + "\n", {
        "n": len(ortak),
        "kappa": kappa,
        "sinif_uyum": sinif_uyum,
        "adim_uyum": adim_uyum,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Cohen kappa ve uyusmazlik raporu")
    parser.add_argument("--write", action="store_true", help="eval/agreement.md dosyasina yaz")
    args = parser.parse_args()

    rapor, ozet = build_report()
    print(rapor)

    if args.write:
        REPORT_PATH.write_text(rapor, encoding="utf-8")
        print(f"-> {REPORT_PATH.relative_to(ROOT)} yazildi")

    if ozet["n"] == 0:
        raise SystemExit(0)


if __name__ == "__main__":
    main()
