"""Deneyin çalıştırılması ve sonuç tablolarının üretilmesi.

Ölçülen tek bileşen dil modelidir (K1–K4). Sembolik doğrulayıcı altın standart
olduğu için sentetik derlemde puanlanmaz; onun sınavı elle yazılan kümede insan
etiketlerine karşı ayrıca yapılır ve ayrı raporlanır.

Üç metrik, giderek zorlaşan üç soruyu yanıtlar:

    M1  Hata var mı?          ikili sınıflama, F1 + yanlış pozitif oranı
    M2  Hangi tür hata?       4 sınıflı, doğruluk + makro-F1
    M3  Hangi adımda?         tam adım eşleşmesi — ASIL BULGU

Her metrik **taban çizgisiyle birlikte** raporlanır. M3 için "hep ilk adım"
taban çizgisi kritiktir: yüksek çıkarsa üretecin konum dolaştırması işlememiş
ve metrik anlamını yitirmiş demektir.

Kullanım:
    python eval/run_experiment.py --dry-run          # sahte istemci, ucretsiz
    python eval/run_experiment.py --arms K1 K2       # gercek cagri
    python eval/run_experiment.py --limit 40 --repeats 1
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

import baselines  # noqa: E402
import generator as gen  # noqa: E402
import handwritten as hw  # noqa: E402
import llm_checker as llm  # noqa: E402
import verifier as vf  # noqa: E402

RESULTS = ROOT / "eval" / "results"
CLASSES = ("H0", "H1", "H2", "H3")


# --------------------------------------------------------------------------
# Veri kümeleri
# --------------------------------------------------------------------------


@dataclass
class Dataset:
    ad: str
    solutions: list[dict[str, Any]]
    labels: list[dict[str, Any]]

    def __len__(self) -> int:
        return len(self.solutions)


def load_synthetic(total: int, seed: int, limit: int | None) -> Dataset:
    sols = gen.generate(total=total, seed=seed)
    if limit:
        sols = sols[:limit]
    return Dataset("sentetik", sols, [s["label"] for s in sols])


def load_handwritten(limit: int | None) -> Dataset:
    """Elle yazılan küme. Gerçek etiket birincil kodlayıcıdan (A1) gelir."""
    sols = hw.load_solutions()
    a1 = hw.load_labels("A1")

    eslesen = [s for s in sols if s["problem_id"] in a1]
    if limit:
        eslesen = eslesen[:limit]
    return Dataset("elle_yazilan", eslesen, [a1[s["problem_id"]] for s in eslesen])


# --------------------------------------------------------------------------
# Metrikler
# --------------------------------------------------------------------------


@dataclass
class Metrics:
    n: int
    gecersiz: int
    m1_f1: float
    m1_kesinlik: float
    m1_duyarlilik: float
    yanlis_pozitif_orani: float
    m2_dogruluk: float
    m2_makro_f1: float
    m3_dogruluk: float
    m3_sinif_dogruyken: float


def _f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    p, r = tp / (tp + fp), tp / (tp + fn)
    return 2 * p * r / (p + r)


def score(
    gercek: Sequence[dict[str, Any]],
    tahmin: Sequence[llm.Prediction],
    solutions: Sequence[dict[str, Any]],
) -> Metrics:
    gecerli = [(g, t, s) for g, t, s in zip(gercek, tahmin, solutions) if t.ok]
    gecersiz = len(tahmin) - len(gecerli)

    if not gecerli:
        nan = float("nan")
        return Metrics(0, gecersiz, nan, nan, nan, nan, nan, nan, nan, nan)

    gs = [g["error_class"] for g, _, _ in gecerli]
    ts = [t.hata_sinifi for _, t, _ in gecerli]

    # M1 — ikili
    tp = sum(1 for g, t in zip(gs, ts) if g != "H0" and t != "H0")
    fp = sum(1 for g, t in zip(gs, ts) if g == "H0" and t != "H0")
    fn = sum(1 for g, t in zip(gs, ts) if g != "H0" and t == "H0")
    h0_sayisi = sum(1 for g in gs if g == "H0")

    # M2 — 4 sınıflı
    dogru = sum(1 for g, t in zip(gs, ts) if g == t)
    makro = []
    for c in CLASSES:
        c_tp = sum(1 for g, t in zip(gs, ts) if g == c and t == c)
        c_fp = sum(1 for g, t in zip(gs, ts) if g != c and t == c)
        c_fn = sum(1 for g, t in zip(gs, ts) if g == c and t != c)
        if c_tp + c_fn > 0:  # kümede hiç örneği olmayan sınıf ortalamaya girmez
            makro.append(_f1(c_tp, c_fp, c_fn))

    # M3 — yalnızca hata içeren örneklerde tanımlı
    hatali = [(g, t) for g, t, _ in gecerli if g["error_class"] != "H0"]
    m3 = (
        sum(1 for g, t in hatali if t.hatali_adim == g.get("error_step")) / len(hatali)
        if hatali
        else float("nan")
    )

    sinif_dogru = [
        (g, t) for g, t in hatali if t.hata_sinifi == g["error_class"]
    ]
    m3_kosullu = (
        sum(1 for g, t in sinif_dogru if t.hatali_adim == g.get("error_step"))
        / len(sinif_dogru)
        if sinif_dogru
        else float("nan")
    )

    return Metrics(
        n=len(gecerli),
        gecersiz=gecersiz,
        m1_f1=_f1(tp, fp, fn),
        m1_kesinlik=tp / (tp + fp) if tp + fp else float("nan"),
        m1_duyarlilik=tp / (tp + fn) if tp + fn else float("nan"),
        yanlis_pozitif_orani=fp / h0_sayisi if h0_sayisi else float("nan"),
        m2_dogruluk=dogru / len(gecerli),
        m2_makro_f1=sum(makro) / len(makro) if makro else float("nan"),
        m3_dogruluk=m3,
        m3_sinif_dogruyken=m3_kosullu,
    )


def confusion(
    gercek: Sequence[dict[str, Any]], tahmin: Sequence[llm.Prediction]
) -> Counter[tuple[str, str]]:
    return Counter(
        (g["error_class"], t.hata_sinifi)
        for g, t in zip(gercek, tahmin)
        if t.ok
    )


# --------------------------------------------------------------------------
# Doğrulayıcının kendi sınavı
# --------------------------------------------------------------------------


def verifier_vs_human(ds: Dataset) -> dict[str, Any] | None:
    """Doğrulayıcıyı insan etiketlerine karşı ölçer.

    Doğrulayıcının GERÇEK sınavı budur. Sentetik derlemdeki yüksek uyum bir
    başarım sonucu değildir; oracle kendi spesifikasyonundan üretilmiş veriyle
    tanım gereği örtüşür. Uyuşmazlıklar teorem kütüphanesindeki eksikleri gösterir.
    """
    if not ds.solutions:
        return None

    sinif = adim = 0
    uyusmazlik: list[dict[str, str]] = []

    for sol, lab in zip(ds.solutions, ds.labels):
        bulgu = vf.verify(sol["figure"], sol["steps"])
        if bulgu.error_class == lab["error_class"]:
            sinif += 1
            if bulgu.error_step == lab.get("error_step"):
                adim += 1
        else:
            uyusmazlik.append({
                "problem_id": sol["problem_id"],
                "insan": lab["error_class"],
                "dogrulayici": bulgu.error_class,
                "sebep": bulgu.reason,
            })

    n = len(ds.solutions)
    return {
        "n": n,
        "sinif_uyumu": sinif / n,
        "adim_uyumu": adim / n,
        "uyusmazlik": uyusmazlik,
    }


# --------------------------------------------------------------------------
# Çalıştırma
# --------------------------------------------------------------------------


def run_arm(
    ds: Dataset,
    arm: str,
    client: llm.LLMClient,
    repeats: int,
    model: str,
    use_cache: bool,
) -> list[list[llm.Prediction]]:
    """Bir kolu `repeats` kez çalıştırır; dış liste tekrarlar, iç liste örnekler."""
    tekrarlar: list[list[llm.Prediction]] = []
    for r in range(repeats):
        tahminler = [
            llm.ask(sol, arm, client, repeat=r, model=model, use_cache=use_cache)
            for sol in ds.solutions
        ]
        tekrarlar.append(tahminler)
    return tekrarlar


def stability(tekrarlar: list[list[llm.Prediction]]) -> float:
    """Tekrarlar arasında aynı sınıfı verme oranı — model kararlılığı."""
    if len(tekrarlar) < 2:
        return float("nan")
    n = len(tekrarlar[0])
    ayni = sum(
        1
        for i in range(n)
        if len({t[i].hata_sinifi for t in tekrarlar if t[i].ok}) == 1
    )
    return ayni / n if n else float("nan")


# --------------------------------------------------------------------------
# Rapor
# --------------------------------------------------------------------------


def _g(x: float) -> str:
    return "—" if x != x else f"{x:.3f}"


def build_report(
    sonuclar: dict[str, dict[str, Any]], model: str, repeats: int
) -> str:
    satirlar = [
        "# Deney Sonuçları",
        "",
        f"Model: `{model}` · tekrar: {repeats} · effort: `{llm.DEFAULT_EFFORT}`",
        "",
        "> Sembolik doğrulayıcı bu tablolarda **yer almaz**: altın standart olduğu "
        "için karşılaştırma nesnesi değildir. Kendi sınavı elle yazılan kümededir "
        "ve aşağıda ayrıca raporlanır.",
        "",
    ]

    for ds_ad, blok in sonuclar.items():
        satirlar += [f"## Küme: {ds_ad} (n = {blok['n']})", ""]

        if blok.get("baselines"):
            satirlar += ["### Taban çizgileri", "", blok["baselines"], ""]

        if blok.get("konum_dagilimi"):
            d = blok["konum_dagilimi"]
            toplam = sum(d.values()) or 1
            en_sik = max(d.values()) / toplam
            satirlar += [
                "Hatalı adımın konum dağılımı: "
                + ", ".join(f"{k}. adım: {v}" for k, v in sorted(d.items())),
                "",
            ]
            if en_sik > 0.6:
                satirlar += [
                    f"> ⚠ Hataların %{en_sik:.0%}'i tek konumda toplanmış. "
                    "M3 bu kümede güvenilir değildir.",
                    "",
                ]

        if not blok.get("arms"):
            satirlar += ["_Bu küme için kol çalıştırılmadı._", ""]
            continue

        satirlar += [
            "### Kollar",
            "",
            "| Kol | n | Geçersiz | M1 · F1 | Yanlış poz. | M2 · Doğruluk | M2 · Makro-F1 | **M3 · Doğruluk** | M3 (sınıf doğruyken) | Kararlılık |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for arm, veri in blok["arms"].items():
            m: Metrics = veri["metrics"]
            satirlar.append(
                f"| **{arm}** | {m.n} | {m.gecersiz} | {_g(m.m1_f1)} | "
                f"{_g(m.yanlis_pozitif_orani)} | {_g(m.m2_dogruluk)} | "
                f"{_g(m.m2_makro_f1)} | **{_g(m.m3_dogruluk)}** | "
                f"{_g(m.m3_sinif_dogruyken)} | {_g(veri['kararlilik'])} |"
            )
        satirlar.append("")

        if "K1" in blok["arms"] and "K2" in blok["arms"]:
            k1: Metrics = blok["arms"]["K1"]["metrics"]
            k2: Metrics = blok["arms"]["K2"]["metrics"]
            satirlar += [
                "### K1 ↔ K2: graf temsilinin katkısı",
                "",
                "Projenin ana iddiasının sınandığı karşılaştırma. İki kol arasındaki "
                "tek fark şekil grafının verilmesidir.",
                "",
                "| Metrik | K1 (grafsız) | K2 (graflı) | Fark |",
                "|---|---|---|---|",
                f"| M1 · F1 | {_g(k1.m1_f1)} | {_g(k2.m1_f1)} | {_g(k2.m1_f1 - k1.m1_f1)} |",
                f"| M2 · Doğruluk | {_g(k1.m2_dogruluk)} | {_g(k2.m2_dogruluk)} | {_g(k2.m2_dogruluk - k1.m2_dogruluk)} |",
                f"| **M3 · Doğruluk** | {_g(k1.m3_dogruluk)} | {_g(k2.m3_dogruluk)} | **{_g(k2.m3_dogruluk - k1.m3_dogruluk)}** |",
                "",
            ]

        for arm, veri in blok["arms"].items():
            satirlar += [f"### Karışıklık matrisi — {arm}", ""]
            satirlar.append("| gerçek \\ tahmin | " + " | ".join(CLASSES) + " |")
            satirlar.append("|---" * (len(CLASSES) + 1) + "|")
            for g in CLASSES:
                hucre = [str(veri["confusion"].get((g, t), 0)) for t in CLASSES]
                satirlar.append(f"| **{g}** | " + " | ".join(hucre) + " |")
            satirlar.append("")

    return "\n".join(satirlar) + "\n"


def write_csv(sonuclar: dict[str, dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "kume", "kol", "n", "gecersiz", "m1_f1", "m1_kesinlik", "m1_duyarlilik",
            "yanlis_pozitif_orani", "m2_dogruluk", "m2_makro_f1",
            "m3_dogruluk", "m3_sinif_dogruyken", "kararlilik",
        ])
        for ds_ad, blok in sonuclar.items():
            for arm, veri in blok.get("arms", {}).items():
                m: Metrics = veri["metrics"]
                w.writerow([
                    ds_ad, arm, m.n, m.gecersiz, m.m1_f1, m.m1_kesinlik,
                    m.m1_duyarlilik, m.yanlis_pozitif_orani, m.m2_dogruluk,
                    m.m2_makro_f1, m.m3_dogruluk, m.m3_sinif_dogruyken,
                    veri["kararlilik"],
                ])


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _utf8_stdout() -> None:
    """Rapor Türkçe ve matematiksel işaretler içerir.

    Windows konsolu varsayılan olarak cp1254 kullanır ve '↔' gibi karakterlerde
    çöker. Dosyalar zaten UTF-8 yazılır; burada yalnızca ekran çıktısı korunur.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def main() -> None:
    _utf8_stdout()
    p = argparse.ArgumentParser(description="LLM deneyini calistir")
    p.add_argument("--arms", nargs="+", default=["K1", "K2", "K3"], choices=llm.ARMS)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--model", default=llm.DEFAULT_MODEL)
    p.add_argument("--total", type=int, default=400, help="sentetik ornek sayisi")
    p.add_argument("--seed", type=int, default=20260906)
    p.add_argument("--limit", type=int, help="kume basina ornek siniri (deneme icin)")
    p.add_argument("--dry-run", action="store_true", help="sahte istemci, cagri yapmaz")
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args()

    kumeler = [
        load_synthetic(args.total, args.seed, args.limit),
        load_handwritten(args.limit),
    ]

    # Maliyet önce gösterilir; deney para harcar.
    toplam_ornek = sum(len(d) for d in kumeler)
    kestirim = llm.estimate_cost(
        toplam_ornek, tuple(args.arms), args.repeats, args.model
    )
    print(f"Kume boyutlari : {', '.join(f'{d.ad}={len(d)}' for d in kumeler)}")
    print(f"Planlanan cagri: {int(kestirim['cagri'])}")
    if args.dry_run:
        print("Mod            : DRY-RUN (sahte istemci, ucret yok)\n")
        client: llm.LLMClient = llm.FakeClient()
    else:
        print(f"Tahmini maliyet: ~${kestirim['toplam_usd']:.2f} ({args.model})")
        print("(onbellekteki cagrilar tekrar ucretlendirilmez)\n")
        client = llm.default_client(model=args.model)

    sonuclar: dict[str, dict[str, Any]] = {}

    for ds in kumeler:
        blok: dict[str, Any] = {"n": len(ds), "arms": {}}

        if not ds.solutions:
            blok["not"] = "kume bos"
            sonuclar[ds.ad] = blok
            print(f"[{ds.ad}] bos, atlandi")
            continue

        blok["baselines"] = baselines.as_markdown(baselines.compute(ds.solutions, ds.labels))
        blok["konum_dagilimi"] = dict(
            baselines.step_position_distribution(ds.solutions, ds.labels)
        )

        for arm in args.arms:
            print(f"[{ds.ad}] {arm} calisiyor ({len(ds)} ornek x {args.repeats})...")
            tekrarlar = run_arm(
                ds, arm, client, args.repeats, args.model, not args.no_cache
            )
            blok["arms"][arm] = {
                "metrics": score(ds.labels, tekrarlar[0], ds.solutions),
                "confusion": confusion(ds.labels, tekrarlar[0]),
                "kararlilik": stability(tekrarlar),
            }

        sonuclar[ds.ad] = blok

    # Doğrulayıcının kendi sınavı — yalnızca elle yazılan kümede anlamlı
    el = next(d for d in kumeler if d.ad == "elle_yazilan")
    dogrulayici = verifier_vs_human(el)

    rapor = build_report(sonuclar, args.model, args.repeats)
    if dogrulayici:
        rapor += (
            f"\n## Doğrulayıcının insan etiketleriyle uyumu\n\n"
            f"n = {dogrulayici['n']} · sınıf uyumu: {dogrulayici['sinif_uyumu']:.1%} · "
            f"adım uyumu: {dogrulayici['adim_uyumu']:.1%}\n\n"
            f"Uyuşmazlık sayısı: {len(dogrulayici['uyusmazlik'])}. "
            f"Her uyuşmazlık teorem kütüphanesindeki bir eksiği gösterir.\n"
        )
    else:
        rapor += (
            "\n## Doğrulayıcının insan etiketleriyle uyumu\n\n"
            "Elle yazılan küme henüz etiketlenmedi; doğrulayıcının gerçek sınavı "
            "bu küme hazır olduğunda yapılacaktır.\n"
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "rapor.md").write_text(rapor, encoding="utf-8")
    write_csv(sonuclar, RESULTS / "sonuclar.csv")
    (RESULTS / "kosullar.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "effort": llm.DEFAULT_EFFORT,
                "arms": args.arms,
                "repeats": args.repeats,
                "seed": args.seed,
                "total": args.total,
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(rapor)
    print(f"-> {(RESULTS / 'rapor.md').relative_to(ROOT)}")
    print(f"-> {(RESULTS / 'sonuclar.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
