"""Gönüllüler için problem föyü.

Elle yazılan kümenin en büyük sürtünmesi "hangi problemi yazayım?" sorusudur.
Bu modül, şablonlardan **yalnızca problemleri** (soru + verilenler + şekil)
çıkarır; çözümleri ve hata varyantlarını taşımaz.

KÖRLÜK — föy şunları içermez:
  - hata sınıfları (H0–H3)
  - çözüm adımları
  - hangi şablon varyantından geldiği

Gönüllü problemi görür, çözümü kendi yazar, hata yapıp yapmayacağına kendi
karar verir. Sınıf dağılımı böylece kendiliğinden oluşur — protokolün istediği
budur (data/handwritten/README.md).

Problem verilenleri varyanttan varyanta değişir: bazı problemlerde diklik
verilmiştir, bazılarında verilmemiştir. Bu kasıtlıdır; verilenlerin eksik
olduğu problemler öğrenci hatasına doğal zemin hazırlar, ama hangi hatanın
yapılacağı gönüllüye bırakılır.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

import problem_templates as pt
import renderer

FAMILIES = ("P1", "P2", "P3", "P4", "P5", "P6")


@dataclass(frozen=True)
class Problem:
    sira: int
    family: str
    kazanim_kodu: str | None
    soru: str
    figure: dict[str, Any]
    coords: dict[str, list[float]]
    bias: str

    @property
    def etiket(self) -> str:
        return f"S{self.sira:02d}"


def _verilen_satirlari(figure: dict[str, Any]) -> list[str]:
    satirlar: list[str] = []
    for seg in figure.get("segments") or []:
        tip = {
            "altitude": "yükseklik",
            "median": "kenarortay",
            "bisector": "açıortay",
        }.get(seg.get("type", "side"))
        if tip:
            satirlar.append(f"[{seg['from']}{seg['to']}] {tip}tir")
        if seg.get("length") is not None:
            satirlar.append(f"|{seg['from']}{seg['to']}| = {seg['length']}")
    for aci in figure.get("angles") or []:
        if aci.get("value") is not None:
            satirlar.append(f"m({aci['vertex']}) = {aci['value']}°")
    for kose in figure.get("perpendicular") or []:
        satirlar.append(f"{kose} köşesinde dik açı")
    for cift in figure.get("congruent_segments") or []:
        satirlar.append(f"|{cift[0]}| = |{cift[1]}|")
    for cift in figure.get("similar") or []:
        satirlar.append(f"{cift[0]} ~ {cift[1]}")
    return satirlar


def _auto_hint(figure: dict[str, Any]) -> dict[str, Any] | None:
    """Şekilde serbest kalmış bir niceliği yanıltıcı gösterecek ipucu türetir.

    `bias` yalnızca VERİLMEMİŞ nicelikleri etkiler; verilenler her hâlükârda
    birebir doğru çizilir (renderer._required_appearance). Dolayısıyla ipucunu
    varyanttan bağımsız seçmek şekli yalan söyletmez — yalnızca serbest bırakılan
    yeri tuzağa çevirir. Ders kitaplarının yaptığı tam olarak budur.
    """
    koseler: list[str] = []
    for seg in figure.get("segments") or []:
        if seg.get("type") == "side":
            for k in (seg["from"], seg["to"]):
                if k not in koseler:
                    koseler.append(k)

    if len(koseler) < 3:
        return None

    if not (figure.get("perpendicular") or []):
        return {"tip": "dik_aci", "kose": koseler[1]}
    if not (figure.get("congruent_segments") or []):
        return {"tip": "ikizkenar", "tepe": koseler[0]}
    return None


def generate(
    n: int = 30,
    seed: int = 20260909,
    templates: list[pt.Template] | None = None,
    misleading_orani: float = 0.5,
) -> list[Problem]:
    """Ailelere dengeli dağılmış `n` problem üretir.

    Varyantlar düzgün dağılımdan çekilir; H0 ile hata varyantları arasında
    ayrım yapılmaz, çünkü buradan yalnızca soru ve şekil alınır. Böylece
    föy hangi hatanın beklendiğine dair hiçbir ipucu taşımaz.
    """
    # Üreteç modülünü import etmemek bilinçlidir: föy, çözüm üretimiyle
    # hiçbir kod paylaşmaz. Yalnızca şablonların soru/şekil kısmını okur.
    from generator import _draw_params, _merge_figure, _subst

    rng = random.Random(seed)
    templates = templates or pt.load_all()
    aile_havuzu = {f: [t for t in templates if t.family == f] for f in FAMILIES}
    aile_havuzu = {f: v for f, v in aile_havuzu.items() if v}

    problemler: list[Problem] = []
    aileler = list(aile_havuzu)

    for i in range(n):
        aile = aileler[i % len(aileler)]
        template = rng.choice(aile_havuzu[aile])
        varyant = rng.choice(template.varyantlar)

        values = _draw_params(template, rng)
        figure = _subst(
            _merge_figure(template.figure_base, varyant.figure_override), values
        )
        soru = _subst(varyant.soru, values)

        # Çizim türü:
        #
        # Verilenleri eksiltilmiş varyantlardan gelen problemler tek başına
        # ÇÖZÜLEMEZ — eksik bilgi kasıtlıdır. Bunlara nötr çizim verilirse
        # gönüllünün elinde ne çözüm ne ipucu kalır; sadece kusurlu bir soru olur.
        # Ders kitabının bu durumda yaptığı şey şekli tuzaklı çizmektir, çünkü
        # öğrencinin eksik bilgiyi oradan "okuması" beklenir.
        #
        # Tam belirlenmiş (H0 kaynaklı) problemlerde çizim serbestçe seçilir.
        eksik_belirlenmis = varyant.sinif != "H0"
        bias = (
            "misleading"
            if eksik_belirlenmis or rng.random() < misleading_orani
            else "neutral"
        )

        hint = _subst(varyant.cizim_ipucu, values) if varyant.cizim_ipucu else None
        if bias == "misleading" and not hint:
            hint = _auto_hint(figure)
        if bias == "misleading" and not hint:
            bias = "neutral"  # serbest kalmış nicelik yoksa tuzak kurulamaz

        coords = renderer.layout(figure, bias, hint, rng)

        problemler.append(
            Problem(
                sira=i + 1,
                family=aile,
                kazanim_kodu=template.kazanim_kodu,
                soru=soru,
                figure=figure,
                coords=coords,
                bias=bias,
            )
        )

    return problemler


def to_html(problemler: list[Problem]) -> str:
    """Yazdırılabilir föy.

    Gönüllü şekli ve verilenleri görür, çözümü boş alana yazar.
    """
    parcalar = [
        "<style>",
        "body{font-family:'Segoe UI',Arial,sans-serif;font-size:11pt;color:#1a1c22;"
        "max-width:190mm;margin:0 auto;padding:10mm}",
        "h1{font-size:16pt;color:#22345e;margin:0 0 4px}",
        ".yonerge{background:#f4f6f9;border-left:4px solid #0e6f66;padding:10px 14px;"
        "font-size:10pt;line-height:1.6;margin:12px 0 20px}",
        ".p{page-break-inside:avoid;border:1px solid #dfe3ea;border-radius:6px;"
        "padding:12px 14px;margin-bottom:14px}",
        ".bas{font-weight:700;color:#22345e;font-size:11.5pt}",
        ".gov{display:flex;gap:16px;align-items:flex-start;margin-top:8px}",
        ".ver{font-size:10pt;color:#5b6472;line-height:1.7}",
        ".cz{border-top:1px dashed #c8cfda;margin-top:10px;padding-top:8px;"
        "font-size:9.5pt;color:#8892a0}",
        ".sat{border-bottom:1px solid #e3e7ee;height:22px}",
        "</style>",
        "<h1>Üçgen Problemleri — Çözüm Föyü</h1>",
        '<div class="yonerge">'
        "Her problem için bir <b>öğrenci çözümü</b> yaz. Bazı çözümlerin "
        "<b>doğru</b>, bazılarının <b>kasıtlı hatalı</b> olsun. Hata yaparken gerçek "
        "bir öğrencinin düşebileceği türden bir hata yapmaya çalış.<br><br>"
        "<b>Hangi hatayı yaptığını yazma.</b> Etiketlemeyi başkası yapacak.<br><br>"
        "Her adımda <i>ne iddia ettiğini</i> ve <i>hangi kurala dayandığını</i> yaz. "
        "Şekiller ölçekli değildir — kenara yazan sayı doğrudur, çizimin görüntüsü "
        "bağlayıcı değildir."
        "</div>",
    ]

    for p in problemler:
        svg = renderer.to_svg(p.figure, p.coords, "Şekil ölçekli değildir.")
        verilenler = "".join(f"• {s}<br>" for s in _verilen_satirlari(p.figure))
        parcalar += [
            '<div class="p">',
            f'<div class="bas">{p.etiket}</div>',
            f"<div>{p.soru}</div>",
            '<div class="gov">',
            f"<div>{svg}</div>",
            f'<div class="ver"><b>Verilenler</b><br>{verilenler or "—"}'
            "<br><i>Bu listede olmayan hiçbir bilgi verilmiş sayılmaz.</i></div>",
            "</div>",
            '<div class="cz">Çözüm adımları (iddia — dayandığı kural)</div>',
            '<div class="sat"></div>' * 4,
            "</div>",
        ]

    return "\n".join(parcalar)


def to_markdown(problemler: list[Problem]) -> str:
    satirlar = ["# Üçgen Problemleri — Çözüm Föyü", ""]
    for p in problemler:
        satirlar += [
            f"## {p.etiket}",
            "",
            p.soru,
            "",
            "**Verilenler**",
            *[f"- {s}" for s in _verilen_satirlari(p.figure)],
            "",
            "_Bu listede olmayan hiçbir bilgi verilmiş sayılmaz._",
            "",
            "Çözüm adımları:",
            "",
            "1. ",
            "2. ",
            "3. ",
            "",
            "---",
            "",
        ]
    return "\n".join(satirlar)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Gonulluler icin problem foyu")
    parser.add_argument("-n", type=int, default=30)
    parser.add_argument("-s", "--seed", type=int, default=20260909)
    parser.add_argument("-o", "--out", default="data/handwritten/foy.html")
    args = parser.parse_args()

    problemler = generate(args.n, args.seed)
    yol = ROOT / args.out
    yol.parent.mkdir(parents=True, exist_ok=True)

    icerik = to_markdown(problemler) if yol.suffix == ".md" else to_html(problemler)
    yol.write_text(icerik, encoding="utf-8")

    from collections import Counter

    dagilim = Counter(p.family for p in problemler)
    print(f"{len(problemler)} problem uretildi")
    print("aile dagilimi:", dict(sorted(dagilim.items())))
    print("cizim:", dict(Counter(p.bias for p in problemler)))
    print("->", yol.relative_to(ROOT))
