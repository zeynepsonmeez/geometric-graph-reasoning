"""Çizim motoru: temsilî şekil üretimi.

Ders kitaplarındaki geometri şekilleri ölçekli değildir — kenara "7" yazılır ama
7 birim çizilmez. H1 (şekle aşırı güvenme) sınıfı tam olarak bu olgu yüzünden vardır.
Şekli ölçekli çizersek çizim hiç yanıltmaz ve vitrin hata sınıfımız anlamsızlaşır.

Bu modül o davranışı bilinçli olarak taklit eder:

    Topoloji ................. birebir doğru
    Verilen nitel ilişkiler .. birebir doğru, işaretli
    Metrik değerler .......... ÖLÇEKLİ DEĞİL, etiketli
    Verilmemiş nitelikler .... SERBEST — bias parametresi belirler

`bias="misleading"` verilmemiş nicelikleri özel durum *gibi görünecek* şekilde
seçer (tuzak); `bias="neutral"` belirgin biçimde genel görünür.

DİKKAT: Üretilen koordinatlar `rendering.coords` altında saklanır ve doğrulayıcı
bu bloğu ASLA okumaz. Çizim bağlayıcı değildir.
Bkz. tests/test_independence.py
"""

from __future__ import annotations

import math
import random
from typing import Any

Point = tuple[float, float]

#: Çizim alanı (SVG kullanıcı birimi). Koordinatlar bu kutuya sığar.
W, H = 240.0, 180.0

#: Nötr çizimde bir açının 90°'ye bu kadar yakın olması yasak (derece).
NEUTRAL_RIGHT_ANGLE_MARGIN = 14.0

#: Nötr çizimde iki kenarın uzunluk oranı bu bandın dışında olmalı.
NEUTRAL_SIDE_RATIO_MARGIN = 0.12


# --------------------------------------------------------------------------
# Geometri yardımcıları
# --------------------------------------------------------------------------


def _angle_at(p: Point, a: Point, b: Point) -> float:
    """p köşesindeki açı (derece)."""
    v1 = (a[0] - p[0], a[1] - p[1])
    v2 = (b[0] - p[0], b[1] - p[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _foot_of_perpendicular(apex: Point, a: Point, b: Point) -> Point:
    """apex noktasının [ab] doğrusu üzerindeki dik izdüşümü."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    denom = dx * dx + dy * dy
    if denom == 0:
        return a
    t = ((apex[0] - ax) * dx + (apex[1] - ay) * dy) / denom
    return (ax + t * dx, ay + t * dy)


def _midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


# --------------------------------------------------------------------------
# Üçgen yerleşimi
# --------------------------------------------------------------------------


def _is_clearly_generic(p0: Point, p1: Point, p2: Point) -> bool:
    """Üçgen belirgin biçimde çeşitkenar ve dikten uzak mı?

    Nötr çizimin görevi hiçbir özel durumu ima etmemektir; tesadüfen dik ya da
    ikizkenar görünen bir "nötr" çizim, deneyin bias değişkenini kirletir.
    """
    for vertex, x, y in ((p0, p1, p2), (p1, p0, p2), (p2, p0, p1)):
        if abs(_angle_at(vertex, x, y) - 90.0) < NEUTRAL_RIGHT_ANGLE_MARGIN:
            return False

    sides = [_dist(p0, p1), _dist(p1, p2), _dist(p0, p2)]
    for i in range(3):
        for j in range(i + 1, 3):
            lo, hi = sorted((sides[i], sides[j]))
            if hi > 0 and (hi - lo) / hi < NEUTRAL_SIDE_RATIO_MARGIN:
                return False
    return True


def _neutral_triangle(rng: random.Random) -> tuple[Point, Point, Point]:
    """Belirgin biçimde genel görünen bir üçgen."""
    for _ in range(200):
        p0 = (rng.uniform(0.06, 0.20) * W, rng.uniform(0.08, 0.22) * H)
        p1 = (rng.uniform(0.78, 0.95) * W, rng.uniform(0.10, 0.30) * H)
        p2 = (rng.uniform(0.30, 0.70) * W, rng.uniform(0.72, 0.94) * H)
        if _is_clearly_generic(p0, p1, p2):
            return p0, p1, p2
    # Rastgele arama tutmazsa elle seçilmiş güvenli bir üçgen
    return (0.10 * W, 0.14 * H), (0.90 * W, 0.24 * H), (0.44 * W, 0.86 * H)


def _right_angle_triangle(rng: random.Random) -> tuple[Point, Point, Point]:
    """Köşesi TAM dik olan üçgen. Dönen sırada ilk nokta dik köşedir."""
    corner = (0.16 * W, 0.16 * H)
    leg_x = rng.uniform(0.55, 0.78) * W
    leg_y = rng.uniform(0.55, 0.78) * H
    return corner, (corner[0] + leg_x, corner[1]), (corner[0], corner[1] + leg_y)


def _isosceles_triangle(rng: random.Random) -> tuple[Point, Point, Point]:
    """Tepe noktasından çıkan iki kenarı EŞİT olan üçgen.

    Dönen sırada ilk nokta tepedir. Bu çizimde yükseklik ayağı ile kenar orta
    noktası çakışır — H1 ve H2 tuzaklarının görsel dayanağı.
    """
    half = rng.uniform(0.28, 0.38) * W
    cx = W / 2
    base_y = 0.84 * H
    apex_y = rng.uniform(0.10, 0.22) * H
    return (cx, apex_y), (cx - half, base_y), (cx + half, base_y)


def _find_triangles(points: list[str], segments: list[dict[str, Any]]) -> list[list[str]]:
    """`side` tipi kenarlardan üçgen çevrimlerini bulur."""
    adj: dict[str, set[str]] = {p: set() for p in points}
    for seg in segments:
        if seg.get("type") != "side":
            continue
        a, b = seg["from"], seg["to"]
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)

    found: list[list[str]] = []
    seen: set[frozenset[str]] = set()
    for a in points:
        for b in adj[a]:
            for c in adj[b]:
                if c != a and c in adj[a]:
                    key = frozenset((a, b, c))
                    if key not in seen:
                        seen.add(key)
                        found.append([a, b, c])
    return found


def _apex_of_congruent(pairs: list[list[str]], points: list[str]) -> str | None:
    """Eş kenar çiftinin ortak köşesini bulur: [["AB","AC"]] -> "A"."""
    for pair in pairs:
        if len(pair) != 2:
            continue
        first, second = pair
        ortak = [p for p in points if p in first and p in second]
        if len(ortak) == 1:
            return ortak[0]
    return None


def _required_appearance(figure: dict[str, Any]) -> tuple[str, str] | None:
    """Verilenlerin çizimde ZORUNLU kıldığı görünüm.

    docs/taksonomi.md §1: metrik değerler ölçekli çizilmez, ancak VERİLEN NİTEL
    İLİŞKİLER birebir doğru çizilir. Verilmiş bir dik açı, dik çizilmelidir —
    aksi hâlde çizim verilenle çelişir ve bu artık "temsilî şekil" değil, hatadır.
    """
    perpendicular = figure.get("perpendicular") or []
    if perpendicular:
        return "dik_aci", perpendicular[0]

    apex = _apex_of_congruent(
        figure.get("congruent_segments") or [], list(figure.get("points", []))
    )
    if apex:
        return "ikizkenar", apex

    return None


def _appearance_for(
    figure: dict[str, Any], bias: str, hint: dict[str, Any] | None
) -> tuple[str, str] | None:
    """Bu şekil için uygulanacak görünüm: (tip, ozel_kose) veya None (genel).

    Öncelik sırası:
      1. Verilenler — bağlayıcıdır, bias ne olursa olsun uygulanır.
      2. Yanıltıcı ipucu — yalnızca verilen yoksa, yani serbest bırakılmış
         bir nicelik varsa devreye girer. Tuzak tam olarak buradadır.
    """
    zorunlu = _required_appearance(figure)
    if zorunlu:
        return zorunlu

    if bias == "misleading" and hint:
        tip = hint.get("tip")
        ozel = hint.get("kose") if tip == "dik_aci" else hint.get("tepe")
        if tip and ozel:
            return tip, ozel

    return None


def _order_for_appearance(
    triangle: list[str], appearance: tuple[str, str] | None
) -> tuple[list[str], str]:
    """Üçgenin köşelerini, özel köşe başa gelecek şekilde sıralar."""
    if not appearance:
        return triangle, "neutral"

    tip, ozel = appearance
    if ozel not in triangle:
        # Görünüm bu üçgene ait değil (örn. iki üçgenli şekilde diğeri)
        return triangle, "neutral"

    return [ozel, *[p for p in triangle if p != ozel]], tip


def layout(
    figure: dict[str, Any],
    bias: str,
    hint: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> dict[str, list[float]]:
    """Şekil için koordinat üretir.

    `bias="misleading"` ise `hint` zorunludur: çizimin NEYİ özel durum gibi
    göstereceğini söyler. `bias="neutral"` ise ipucu yok sayılır.

    Verilen ölçüler koordinatlara YANSITILMAZ — şekil ölçekli değildir.
    """
    rng = rng or random.Random()
    points: list[str] = list(figure.get("points", []))
    segments: list[dict[str, Any]] = list(figure.get("segments", []))

    coords: dict[str, Point] = {}
    triangles = _find_triangles(points, segments)
    appearance = _appearance_for(figure, bias, hint)

    for index, triangle in enumerate(triangles):
        ordered, tip = _order_for_appearance(triangle, appearance)

        if tip == "dik_aci":
            placed = _right_angle_triangle(rng)
        elif tip == "ikizkenar":
            placed = _isosceles_triangle(rng)
        else:
            placed = _neutral_triangle(rng)

        # Birden fazla üçgen varsa (P6) yan yana yerleştir
        offset_x = index * (W + 0.18 * W)
        for name, (x, y) in zip(ordered, placed):
            coords[name] = (x + offset_x, y)

    # Türetilmiş noktalar: yükseklik / kenarortay / açıortay ayakları
    for seg in segments:
        tip = seg.get("type")
        if tip not in ("altitude", "median", "bisector"):
            continue

        apex, foot = seg["from"], seg["to"]
        if apex not in coords or foot in coords:
            continue

        triangle = next((t for t in triangles if apex in t), None)
        if triangle is None:
            continue

        a, b = [coords[p] for p in triangle if p != apex]
        if tip == "altitude":
            coords[foot] = _foot_of_perpendicular(coords[apex], a, b)
        else:
            # Kenarortay tam orta noktaya, açıortay ona yakın ama eşit değil.
            # Açıortay ayağını orta noktadan kaydırmak, ikisinin görsel olarak
            # ayırt edilebilmesini sağlar (H2'nin çizimden okunamaması için).
            mid = _midpoint(a, b)
            if tip == "median":
                coords[foot] = mid
            else:
                t = rng.choice((0.38, 0.62))
                coords[foot] = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))

    # Yerleştirilememiş noktalar (beklenmedik şekiller için güvenli varsayılan)
    for p in points:
        coords.setdefault(p, (W / 2, H / 2))

    return {name: [round(x, 2), round(y, 2)] for name, (x, y) in coords.items()}


# --------------------------------------------------------------------------
# SVG çizimi
# --------------------------------------------------------------------------

_SVG_STYLE = (
    "font-family:'Segoe UI',Arial,sans-serif;font-size:13px"
)


def _label_offset(p: Point, center: Point, d: float = 17.0) -> Point:
    """Etiketi şeklin merkezinden dışarı doğru kaydırır."""
    dx, dy = p[0] - center[0], p[1] - center[1]
    n = math.hypot(dx, dy) or 1.0
    return (p[0] + d * dx / n, p[1] + d * dy / n)


def to_svg(
    figure: dict[str, Any],
    coords: dict[str, list[float]],
    note: str = "Şekil ölçekli değildir.",
    scale: float = 1.0,
) -> str:
    """Şekli SVG olarak çizer.

    Uzunluk ve açı etiketleri verilenlerden yazılır; koordinatlardan ÖLÇÜLMEZ.
    Bu ayrım kasıtlıdır: etiket doğruyu söyler, çizim söylemez.

    `scale` yalnızca çıktı boyutunu büyütür; viewBox ve dolayısıyla geometri
    değişmez. Sunumda uzaktan okunabilmesi için arayüz bunu 2 civarında kullanır.
    """
    segments = figure.get("segments", [])
    pts = {k: (v[0], v[1]) for k, v in coords.items()}
    if not pts:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"></svg>'

    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    pad = 26.0
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad * 1.4
    width, height = max_x - min_x, max_y - min_y
    center = (sum(xs) / len(xs), sum(ys) / len(ys))

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{min_x:.1f} {min_y:.1f} {width:.1f} {height:.1f}" '
        f'width="{width * scale:.0f}" height="{height * scale:.0f}" '
        f'style="{_SVG_STYLE}">'
    ]

    # Üçgen yüzeyleri
    for triangle in _find_triangles(list(figure.get("points", [])), segments):
        poly = " ".join(f"{pts[p][0]:.1f},{pts[p][1]:.1f}" for p in triangle if p in pts)
        out.append(f'<polygon points="{poly}" fill="#dde6f4" stroke="none"/>')

    # Kenarlar
    dash = {"altitude": "5,3", "median": "5,3", "bisector": "2,3"}
    color = {"side": "#22345e", "altitude": "#a3251f", "median": "#0e6f66", "bisector": "#5a3a86"}
    for seg in segments:
        a, b = seg["from"], seg["to"]
        if a not in pts or b not in pts:
            continue
        tip = seg.get("type", "side")
        stroke = color.get(tip, "#22345e")
        extra = f' stroke-dasharray="{dash[tip]}"' if tip in dash else ""
        out.append(
            f'<line x1="{pts[a][0]:.1f}" y1="{pts[a][1]:.1f}" '
            f'x2="{pts[b][0]:.1f}" y2="{pts[b][1]:.1f}" '
            f'stroke="{stroke}" stroke-width="2.6"{extra}/>'
        )

        # Uzunluk etiketi — VERİLENDEN yazılır, çizimden ölçülmez
        if seg.get("length") is not None:
            mx, my = _midpoint(pts[a], pts[b])
            lx, ly = _label_offset((mx, my), center, 11.0)
            out.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#3d4757" font-size="13.5" '
                f'font-weight="600" text-anchor="middle">{seg["length"]}</text>'
            )

    # Verilen dik açı işaretleri (yalnızca figure.perpendicular'dakiler)
    for vertex in figure.get("perpendicular", []):
        if vertex not in pts:
            continue
        x, y = pts[vertex]
        out.append(
            f'<rect x="{x - 1:.1f}" y="{y - 14:.1f}" width="14" height="14" '
            f'fill="none" stroke="#22345e" stroke-width="2"/>'
        )

    # Noktalar ve adları
    for name, (x, y) in pts.items():
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="#22345e"/>')
        lx, ly = _label_offset((x, y), center)
        out.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#22345e" font-weight="700" '
            f'font-size="15" text-anchor="middle">{name}</text>'
        )

    # Açı etiketleri
    for angle in figure.get("angles", []):
        vertex, value = angle.get("vertex"), angle.get("value")
        if value is None or vertex not in pts:
            continue
        x, y = pts[vertex]
        ix, iy = _label_offset((x, y), center, -19.0)
        out.append(
            f'<text x="{ix:.1f}" y="{iy:.1f}" fill="#9a6100" font-size="13.5" '
            f'font-weight="600" text-anchor="middle">{value}°</text>'
        )

    out.append(
        f'<text x="{max_x - 4:.1f}" y="{max_y - 6:.1f}" fill="#a3251f" '
        f'font-size="9" text-anchor="end">{note}</text>'
    )
    out.append("</svg>")
    return "\n".join(out)
