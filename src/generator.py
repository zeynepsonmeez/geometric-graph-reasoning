"""Sentetik üreteç.

Şablonlardan (`data/problems/*.json`) dengeli dağılımlı örnek üretir. Her örnek
`schema/solution.schema.json` ile uyumlu tek bir JSON dosyasıdır.

Etiket üretim anında BİLİNEREK oluşur; sonradan etiketleme yoktur.

DİKKAT — mimari kuralı:
    Bu modül `verifier.py` ve `theorems.py` modüllerini import ETMEZ.
    Üreteç hatayı KURAR, doğrulayıcı geçerliliği DENETLER. Aynı kodu
    paylaşırlarsa doğrulayıcı tanım gereği %100 doğruluk alır ve sonuç
    anlamsızlaşır. Paylaşılan tek şey docs/taksonomi.md spesifikasyonudur.
    Bkz. tests/test_independence.py

Şablon izi (docs/taksonomi.md §7): üreteç köşe adlarını, sayıları, adım sayısını
ve HATALI ADIMIN KONUMUNU çeşitlendirir. Son madde kritiktir — hata hep 1. adımda
olursa model "ilk adımı söyle" diyerek yüksek M3 skoru alır ve metrik anlamsızlaşır.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

import problem_templates as pt
import renderer

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "synthetic"

#: Köşe adı üçlüleri. Sabit ABC yerine dolaşarak ad ezberini engeller.
VERTEX_POOL: list[tuple[str, str, str]] = [
    ("A", "B", "C"), ("K", "L", "M"), ("D", "E", "F"), ("P", "Q", "R"),
    ("X", "Y", "Z"), ("S", "T", "U"), ("A", "C", "E"), ("B", "D", "F"),
    ("K", "N", "P"), ("L", "R", "T"),
]

def _make_filler(figure: dict[str, Any]) -> dict[str, str] | None:
    """Sonuca katkısız ama GEÇERLİ bir ara adım üretir.

    Zincir uzunluğunun ipucu olmasını engeller ve hatalı adımın konumunu kaydırır.
    Köşe adları şeklin kendisinden okunur; yer tutucu adları şablondan şablona
    değiştiği için (V0.. / W0..) sabit kodlanamaz.
    """
    triangles = renderer._find_triangles(
        list(figure.get("points", [])), figure.get("segments", [])
    )
    if not triangles:
        return None
    a, b, c = triangles[0]
    return {
        "claim": f"m({a}) + m({b}) + m({c}) = 180",
        "rule": "ic_acilar_toplami",
    }

PLACEHOLDER_ONLY = re.compile(r"^\{([A-Za-z][A-Za-z0-9_]*)\}$")

CLASSES = ("H0", "H1", "H2", "H3")


# --------------------------------------------------------------------------
# Parametre üretimi
# --------------------------------------------------------------------------


def _literal_points(template: pt.Template) -> set[str]:
    """Şablonda sabit yazılmış yardımcı nokta adları ("H", "D" gibi).

    Köşe adları bunlarla çakışamaz: P5-T02'nin açıortay ayağı "D" iken köşe
    üçlüsü de ("D","E","F") çekilirse aynı ad iki noktaya verilir ve şekil bozulur.
    """
    return {
        p for p in template.figure_base.get("points", [])
        if isinstance(p, str) and not PLACEHOLDER_ONLY.match(p)
    }


def _draw_params(template: pt.Template, rng: random.Random) -> dict[str, Any]:
    """Şablonun parametrelerini kısıtları sağlayana kadar rastgele çeker."""
    yasakli = _literal_points(template)

    for _ in range(500):
        values: dict[str, Any] = {}
        for name, spec in template.parametreler.items():
            tip = spec["tip"]
            if tip == "vertex_triple":
                for i, letter in enumerate(rng.choice(VERTEX_POOL)):
                    values[f"{name}{i}"] = letter
            elif tip == "vertex_sextuple":
                # İki üçgenin köşe adları AYRIK olmalı; havuzdaki üçlüler harf
                # paylaşabildiği için (KLM ve KNP gibi) kesişim denetlenir.
                for _ in range(50):
                    first, second = rng.sample(VERTEX_POOL, 2)
                    if not set(first) & set(second):
                        break
                else:
                    harfler = rng.sample("ABCDEFKLMNPRSTUXYZ", 6)
                    first, second = tuple(harfler[:3]), tuple(harfler[3:])
                for i, letter in enumerate([*first, *second]):
                    values[f"{name}{i}"] = letter
            else:
                step = spec.get("adim", 1)
                lo = -(-spec["min"] // step)
                hi = spec["max"] // step
                values[name] = rng.randint(lo, hi) * step

        koseler = [v for v in values.values() if isinstance(v, str)]
        if set(koseler) & yasakli:
            continue
        if len(koseler) != len(set(koseler)):
            continue

        if _satisfies(template.kisitlar, values):
            return values

    raise RuntimeError(f"{template.template_id}: kisitlar saglanamadi")


def _satisfies(constraints: list[str], values: dict[str, Any]) -> bool:
    """Kısıtları değerlendirir.

    İfadeler depoya elle yazılmış şablon verisinden gelir, dış girdiden değil;
    yine de builtins kapatılarak değerlendirilir.
    """
    numeric = {k: v for k, v in values.items() if isinstance(v, int)}
    for expression in constraints:
        try:
            if not eval(expression, {"__builtins__": {}}, numeric):  # noqa: S307
                return False
        except NameError:
            return False
    return True


# --------------------------------------------------------------------------
# Yer tutucu yerleştirme
# --------------------------------------------------------------------------


def _subst(node: Any, values: dict[str, Any]) -> Any:
    """{yer_tutucu} adlarını değerleriyle değiştirir.

    Tümü tek bir sayısal yer tutucudan ibaret olan dizeler ("{a}") sayıya
    dönüştürülür; şemada `length` alanı sayı bekler.
    """
    if isinstance(node, str):
        match = PLACEHOLDER_ONLY.match(node)
        if match and isinstance(values.get(match.group(1)), int):
            return values[match.group(1)]
        return re.sub(
            r"\{([A-Za-z][A-Za-z0-9_]*)\}",
            lambda m: str(values.get(m.group(1), m.group(0))),
            node,
        )
    if isinstance(node, dict):
        return {k: _subst(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [_subst(v, values) for v in node]
    return node


# --------------------------------------------------------------------------
# Örnek kurma
# --------------------------------------------------------------------------


def _merge_figure(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    figure = json.loads(json.dumps(base))
    figure.update(json.loads(json.dumps(override)))
    figure.setdefault("angles", [])
    figure.setdefault("perpendicular", [])
    figure.setdefault("congruent_segments", [])
    figure.setdefault("similar", [])
    return figure


def _insert_filler(
    steps: list[dict[str, Any]],
    hatali_adim: str | None,
    figure: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    """Adımların ÖNÜNE geçerli bir dolgu adımı ekler ve id'leri yeniden numaralar.

    Amaç hatanın konumunu dolaştırmaktır: hata hep 1. adımda olursa M3 metriği
    anlamsızlaşır (docs/taksonomi.md §7).
    """
    if len(steps) >= 4:
        return steps, hatali_adim

    filler = _make_filler(figure)
    if filler is None:
        return steps, hatali_adim

    yeni = [{"id": "_f", "claim": filler["claim"], "rule": filler["rule"], "depends_on": []}, *steps]

    remap = {old["id"]: f"s{i + 1}" for i, old in enumerate(yeni)}
    renumbered = [
        {
            "id": remap[s["id"]],
            "claim": s["claim"],
            "rule": s["rule"],
            "depends_on": [remap[d] for d in s["depends_on"]],
        }
        for s in yeni
    ]
    return renumbered, (remap[hatali_adim] if hatali_adim else None)


def build(
    template: pt.Template,
    variant: pt.Variant,
    index: int,
    rng: random.Random,
) -> dict[str, Any]:
    """Tek bir somut örnek kurar."""
    values = _draw_params(template, rng)

    figure = _subst(_merge_figure(template.figure_base, variant.figure_override), values)
    steps = _subst(variant.steps, values)
    hatali_adim = _subst(variant.hatali_adim, values) if variant.hatali_adim else None

    # Dolgu adımı, hatanın konumunu dolaştırmak için yaklaşık yarı yarıya eklenir
    if rng.random() < 0.5:
        steps, hatali_adim = _insert_filler(steps, hatali_adim, figure)

    hint = _subst(variant.cizim_ipucu, values) if variant.cizim_ipucu else None
    coords = renderer.layout(figure, variant.bias, hint, rng)

    return {
        "problem_id": f"{template.family}-{index:04d}",
        "family": template.family,
        "kazanim_kodu": template.kazanim_kodu,
        "soru": _subst(variant.soru, values),
        "figure": figure,
        "rendering": {
            "coords": coords,
            "bias": variant.bias,
            "note": "Şekil ölçekli değildir.",
        },
        "steps": steps,
        "label": {
            "error_class": variant.sinif,
            "error_step": hatali_adim,
            "source": "generator",
            "arithmetic_flag": False,
        },
    }


# --------------------------------------------------------------------------
# Toplu üretim
# --------------------------------------------------------------------------


def _sources_by_class(
    templates: list[pt.Template],
) -> dict[str, list[tuple[pt.Template, pt.Variant]]]:
    sources: dict[str, list[tuple[pt.Template, pt.Variant]]] = {c: [] for c in CLASSES}
    for template in templates:
        for variant in template.varyantlar:
            sources[variant.sinif].append((template, variant))
    return sources


def generate(
    total: int = 400,
    seed: int = 20260906,
    templates: list[pt.Template] | None = None,
) -> list[dict[str, Any]]:
    """Dört sınıfa eşit bölünmüş `total` örnek üretir."""
    rng = random.Random(seed)
    templates = templates or pt.load_all()
    sources = _sources_by_class(templates)

    bos = [c for c in CLASSES if not sources[c]]
    if bos:
        raise RuntimeError(f"Su siniflar icin hic varyant yok: {bos}")

    per_class = total // len(CLASSES)
    solutions: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()

    for sinif in CLASSES:
        havuz = sources[sinif]
        for i in range(per_class):
            # Sırayla dolaşmak, tek bir şablonun sınıfa hâkim olmasını engeller
            template, variant = havuz[i % len(havuz)]
            counters[template.family] += 1
            solutions.append(build(template, variant, counters[template.family], rng))

    rng.shuffle(solutions)
    return solutions


def write(solutions: list[dict[str, Any]], out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    for i, solution in enumerate(solutions, start=1):
        path = out_dir / f"{i:04d}_{solution['problem_id']}.json"
        path.write_text(
            json.dumps(solution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def summarize(solutions: list[dict[str, Any]]) -> str:
    siniflar = Counter(s["label"]["error_class"] for s in solutions)
    aileler = Counter(s["family"] for s in solutions)
    bias = Counter(s["rendering"]["bias"] for s in solutions)

    konumlar: Counter[int] = Counter()
    for s in solutions:
        adim = s["label"]["error_step"]
        if adim:
            konumlar[[x["id"] for x in s["steps"]].index(adim) + 1] += 1

    satirlar = [
        f"toplam        : {len(solutions)}",
        f"siniflar      : {dict(sorted(siniflar.items()))}",
        f"aileler       : {dict(sorted(aileler.items()))}",
        f"cizim bias    : {dict(sorted(bias.items()))}",
        f"hata konumu   : {dict(sorted(konumlar.items()))}",
    ]

    # Sınıf-aile çapraz dağılımı: yapay korelasyon denetimi
    capraz: dict[str, set[str]] = {}
    for s in solutions:
        if s["label"]["error_class"] != "H0":
            capraz.setdefault(s["label"]["error_class"], set()).add(s["family"])
    for sinif in ("H1", "H2", "H3"):
        aile = sorted(capraz.get(sinif, set()))
        satirlar.append(f"{sinif} aileleri  : {aile} ({len(aile)} aile)")

    return "\n".join(satirlar)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentetik ornek uretici")
    parser.add_argument("-n", "--total", type=int, default=400)
    parser.add_argument("-s", "--seed", type=int, default=20260906)
    parser.add_argument("--dry-run", action="store_true", help="dosyaya yazma")
    args = parser.parse_args()

    solutions = generate(total=args.total, seed=args.seed)
    print(summarize(solutions))

    if args.dry_run:
        print("\n(dry-run: dosya yazilmadi)")
        return

    write(solutions)
    print(f"\n{len(solutions)} ornek yazildi -> {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
