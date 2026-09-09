"""Akıl yürütme grafının görselleştirilmesi.

Demonun asıl anlatısı burada: hata bir "yanlış" damgası değil, graf üzerinde
**konumu belli** bir bozukluktur. Hatalı adım kırmızı, ona bağlı olan ve bu
yüzden kirlenmiş adımlar soluk gösterilir.

Streamlit'ten bağımsızdır; saf SVG döndürür ve testlerde doğrudan çağrılabilir.
"""

from __future__ import annotations

from typing import Any, Sequence

KUTU_G, KUTU_Y = 250.0, 44.0
DIKEY_ARA = 26.0
KENAR = 14.0

RENK = {
    "gecerli": ("#e8eef7", "#22345e", "#22345e"),
    "hatali": ("#fdecea", "#a3251f", "#a3251f"),
    "kirlenmis": ("#f4f6f9", "#c8cfda", "#8892a0"),
}


def _kirlenmisler(steps: Sequence[dict[str, Any]], error_step: str | None) -> set[str]:
    """Hatalı adıma doğrudan ya da dolaylı bağlı adımlar.

    docs/taksonomi.md §4.1: bunlar ayrıca hata sayılmaz, ama sonuçları
    güvenilir değildir — arayüzde bunu göstermek öğrenciye doğru mesajı verir.
    """
    if not error_step:
        return set()

    kirli = {error_step}
    for _ in range(len(steps)):
        for st in steps:
            if set(st.get("depends_on") or []) & kirli:
                kirli.add(st["id"])
    return kirli - {error_step}


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _kisalt(text: str, limit: int = 34) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def reasoning_graph_svg(
    steps: Sequence[dict[str, Any]],
    error_step: str | None = None,
    width: float = 300.0,
) -> str:
    """Akıl yürütme grafını dikey bir DAG olarak çizer."""
    if not steps:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'

    kirli = _kirlenmisler(steps, error_step)
    yukseklik = len(steps) * (KUTU_Y + DIKEY_ARA) + KENAR
    sol = (width - KUTU_G) / 2

    konum: dict[str, tuple[float, float]] = {}
    for i, st in enumerate(steps):
        konum[st["id"]] = (sol, KENAR + i * (KUTU_Y + DIKEY_ARA))

    parcalar = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{yukseklik:.0f}" viewBox="0 0 {width:.0f} {yukseklik:.0f}" '
        f'font-family="Segoe UI, Arial, sans-serif">',
        '<defs><marker id="ok" markerWidth="8" markerHeight="8" refX="7" refY="3" '
        'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#8892a0"/></marker></defs>',
    ]

    # Bağımlılık okları
    for st in steps:
        x2, y2 = konum[st["id"]]
        for dep in st.get("depends_on") or []:
            if dep not in konum:
                continue
            x1, y1 = konum[dep]
            parcalar.append(
                f'<line x1="{x1 + KUTU_G / 2:.1f}" y1="{y1 + KUTU_Y:.1f}" '
                f'x2="{x2 + KUTU_G / 2:.1f}" y2="{y2 - 3:.1f}" '
                f'stroke="#8892a0" stroke-width="1.4" marker-end="url(#ok)"/>'
            )

    # Adım kutuları
    for st in steps:
        x, y = konum[st["id"]]
        if st["id"] == error_step:
            durum = "hatali"
        elif st["id"] in kirli:
            durum = "kirlenmis"
        else:
            durum = "gecerli"
        dolgu, cizgi, yazi = RENK[durum]
        kalinlik = 2.2 if durum == "hatali" else 1.4
        kesik = ' stroke-dasharray="4,3"' if durum == "kirlenmis" else ""

        parcalar.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{KUTU_G}" height="{KUTU_Y}" '
            f'rx="6" fill="{dolgu}" stroke="{cizgi}" stroke-width="{kalinlik}"{kesik}/>'
        )

        isaret = " ✗" if durum == "hatali" else ""
        parcalar.append(
            f'<text x="{x + 10:.1f}" y="{y + 18:.1f}" font-size="11" '
            f'font-weight="700" fill="{yazi}">{st["id"]}{isaret}</text>'
        )
        parcalar.append(
            f'<text x="{x + 42:.1f}" y="{y + 18:.1f}" font-size="10.5" '
            f'fill="{yazi}">{_escape(_kisalt(st.get("claim", "")))}</text>'
        )
        parcalar.append(
            f'<text x="{x + 10:.1f}" y="{y + 34:.1f}" font-size="9" '
            f'fill="#5b6472">{_escape(st.get("rule", ""))}</text>'
        )

    parcalar.append("</svg>")
    return "\n".join(parcalar)


def legend_html() -> str:
    return (
        '<div style="font:11px Segoe UI,Arial;color:#5b6472;line-height:1.9">'
        '<span style="display:inline-block;width:11px;height:11px;background:#fdecea;'
        'border:2px solid #a3251f;border-radius:2px;vertical-align:-1px"></span> hatalı adım'
        '&nbsp;&nbsp;'
        '<span style="display:inline-block;width:11px;height:11px;background:#f4f6f9;'
        'border:1px dashed #c8cfda;border-radius:2px;vertical-align:-1px"></span> kirlenmiş'
        '&nbsp;&nbsp;'
        '<span style="display:inline-block;width:11px;height:11px;background:#e8eef7;'
        'border:1px solid #22345e;border-radius:2px;vertical-align:-1px"></span> geçerli'
        "</div>"
    )
