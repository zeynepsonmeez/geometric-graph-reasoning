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


def _embed(svg: str, x: float, y: float, w: float, h: float) -> str:
    """Bir SVG'yi başka bir SVG'nin içine konumlandırarak gömer.

    İç içe `<svg>` kendi viewBox'ını korur ve ölçeklemeyi kendisi halleder;
    böylece çizim motorunun çıktısını yeniden üretmek gerekmez.
    """
    import re

    ic = re.sub(r'\swidth="[^"]*"', "", svg, count=1)
    ic = re.sub(r'\sheight="[^"]*"', "", ic, count=1)
    return ic.replace(
        "<svg ",
        f'<svg x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" '
        'preserveAspectRatio="xMidYMid meet" ',
        1,
    )


#: Hangi hata sınıfı, şekil grafındaki hangi eksikliğe işaret ediyor?
EKSIK_METNI = {
    "H1": "Bu bilgi verilenlerde YOK",
    "H2": "Eleman tipi uyuşmuyor",
    "H3": "Teoremin ön koşulu sağlanmıyor",
}


def dual_graph_svg(
    figure: dict[str, Any],
    figure_svg: str,
    steps: Sequence[dict[str, Any]],
    error_step: str | None = None,
    error_class: str = "H0",
    width: float = 920.0,
) -> str:
    """Çift graf görseli — projenin tezi tek resimde.

    Solda şekil grafı (ne verildi), sağda akıl yürütme grafı (nasıl ilerledi).
    Hata varsa ikisi arasına kırmızı kesikli bir bağ çizilir: hatalı adım,
    şekil grafında **bulunmayan** bir şeye dayanıyor.

    Bu, sistemin "yanlış" demek yerine hatayı KONUMLANDIRDIĞINI tek bakışta
    gösterir — demonun anlatısı budur.
    """
    n = max(len(steps), 1)
    yukseklik = max(300.0, KENAR * 2 + 46 + n * (KUTU_Y + DIKEY_ARA))

    sol_g = width * 0.40
    sag_g = width - sol_g
    basl_y = 26.0

    kirli = _kirlenmisler(steps, error_step)
    hatali_index = next(
        (i for i, s in enumerate(steps) if s["id"] == error_step), None
    )

    p: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'viewBox="0 0 {width:.0f} {yukseklik:.0f}" '
        f'font-family="Segoe UI, Arial, sans-serif">',
        '<defs><marker id="dok" markerWidth="8" markerHeight="8" refX="7" refY="3" '
        'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#8892a0"/></marker>'
        '<marker id="rok" markerWidth="9" markerHeight="9" refX="8" refY="3.2" '
        'orient="auto"><path d="M0,0 L8,3.2 L0,6.4 z" fill="#a3251f"/></marker></defs>',
        f'<rect x="0" y="0" width="{width:.0f}" height="{yukseklik:.0f}" fill="#ffffff"/>',
    ]

    # Panel başlıkları
    p.append(
        f'<text x="18" y="{basl_y}" font-size="12" font-weight="700" fill="#22345e" '
        f'letter-spacing="1.1">ŞEKİL GRAFI</text>'
        f'<text x="18" y="{basl_y + 16}" font-size="10.5" fill="#5b6472">'
        f"ne verildi?</text>"
    )
    p.append(
        f'<text x="{sol_g + 18:.0f}" y="{basl_y}" font-size="12" font-weight="700" '
        f'fill="#0e6f66" letter-spacing="1.1">AKIL YÜRÜTME GRAFI</text>'
        f'<text x="{sol_g + 18:.0f}" y="{basl_y + 16}" font-size="10.5" fill="#5b6472">'
        f"nasıl ilerledi?</text>"
    )
    p.append(
        f'<line x1="{sol_g:.0f}" y1="{basl_y + 26:.0f}" x2="{sol_g:.0f}" '
        f'y2="{yukseklik - 14:.0f}" stroke="#e3e7ee" stroke-width="1.5"/>'
    )

    # Sol panel: şekil
    p.append(_embed(figure_svg, 14, basl_y + 30, sol_g - 30, yukseklik - basl_y - 48))

    # Sağ panel: adımlar
    # Adım sütunu, tutarsızlık rozetine ve okuna yer bırakacak kadar sağda başlar.
    sol_x = sol_g + 34
    # Kutu genişliği sabit: rozet SAĞINA konacak, o alan her örnekte aynı
    # kalmalı ki kutular örnekten örneğe zıplamasın.
    kutu_g = KUTU_G
    ust_y = basl_y + 34
    konum: dict[str, tuple[float, float]] = {}
    for i, st in enumerate(steps):
        konum[st["id"]] = (sol_x, ust_y + i * (KUTU_Y + DIKEY_ARA))

    for st in steps:
        x2, y2 = konum[st["id"]]
        for dep in st.get("depends_on") or []:
            if dep not in konum:
                continue
            x1, y1 = konum[dep]
            p.append(
                f'<line x1="{x1 + kutu_g / 2:.1f}" y1="{y1 + KUTU_Y:.1f}" '
                f'x2="{x2 + kutu_g / 2:.1f}" y2="{y2 - 3:.1f}" '
                f'stroke="#8892a0" stroke-width="1.5" marker-end="url(#dok)"/>'
            )

    for st in steps:
        x, y = konum[st["id"]]
        if st["id"] == error_step:
            durum = "hatali"
        elif st["id"] in kirli:
            durum = "kirlenmis"
        else:
            durum = "gecerli"
        dolgu, cizgi, yazi = RENK[durum]

        p.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{kutu_g:.0f}" height="{KUTU_Y}" '
            f'rx="7" fill="{dolgu}" stroke="{cizgi}" '
            f'stroke-width="{2.6 if durum == "hatali" else 1.4}"'
            f'{" stroke-dasharray=\'4,3\'" if durum == "kirlenmis" else ""}/>'
        )
        isaret = " ✗" if durum == "hatali" else ""
        p.append(
            f'<text x="{x + 12:.1f}" y="{y + 19:.1f}" font-size="12" '
            f'font-weight="700" fill="{yazi}">{st["id"]}{isaret}</text>'
            f'<text x="{x + 48:.1f}" y="{y + 19:.1f}" font-size="11.5" fill="{yazi}">'
            f'{_escape(_kisalt(st.get("claim", ""), 30))}</text>'
            f'<text x="{x + 12:.1f}" y="{y + 35:.1f}" font-size="9.5" fill="#5b6472">'
            f'{_escape(st.get("rule", ""))}</text>'
        )

    # Tutarsızlık bağı — projenin merkezî fikri.
    #
    # Rozet hatalı adımın SAĞINDA durur. Üstüne konsaydı adımlar arası
    # bağımlılık okunu örterdi; sol panele konsaydı iki üçgenli şekillerin
    # üstüne binerdi. Sağ şerit her örnekte boş olduğu için güvenli yer orası.
    #
    # Ok, bölücüden çıkıp hatalı adıma girer: bu adım, şekil grafında
    # bulunmayan bir şeye dayanıyor.
    if hatali_index is not None and error_class in EKSIK_METNI:
        hx, hy = konum[steps[hatali_index]["id"]]
        orta_y = hy + KUTU_Y / 2

        p.append(
            f'<circle cx="{sol_g:.0f}" cy="{orta_y:.0f}" r="4.5" fill="#a3251f"/>'
            f'<line x1="{sol_g + 5:.0f}" y1="{orta_y:.0f}" x2="{hx - 7:.0f}" '
            f'y2="{orta_y:.0f}" stroke="#a3251f" stroke-width="2.2" '
            f'stroke-dasharray="5,4" marker-end="url(#rok)"/>'
        )

        rozet_x = hx + kutu_g + 12
        rozet_g = max(120.0, width - rozet_x - 14)
        p.append(
            f'<rect x="{rozet_x:.0f}" y="{orta_y - 12:.0f}" width="{rozet_g:.0f}" '
            f'height="24" rx="12" fill="#fdecea" stroke="#a3251f" stroke-width="1.3"/>'
            f'<text x="{rozet_x + rozet_g / 2:.0f}" y="{orta_y + 4:.0f}" font-size="10.5" '
            f'font-weight="600" fill="#a3251f" text-anchor="middle">'
            f'{EKSIK_METNI[error_class]}</text>'
        )

    p.append("</svg>")
    return "\n".join(p)


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
