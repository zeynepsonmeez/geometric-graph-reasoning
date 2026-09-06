"""Teorem kütüphanesi.

Sistemin tanıdığı çıkarım kurallarını, her birinin ön koşullarıyla birlikte tutar.
Doğrulayıcının bilgi tabanıdır: bir adımın geçerliliği, kullandığı teoremin
ön koşullarının `figure` bloğu tarafından sağlanıp sağlanmadığına bakılarak belirlenir.

Kapsam: 9. sınıf üçgenler ünitesi, hesaplama tipi problemler (bkz. docs/taksonomi.md).

DİKKAT: Bu modül `generator.py` tarafından import EDİLMEZ. Üreteç, hataları
docs/taksonomi.md spesifikasyonundan bağımsız olarak kurar. Bkz. tests/test_independence.py
"""

from dataclasses import dataclass, field
from enum import Enum


class ErrorClass(str, Enum):
    """docs/taksonomi.md §2"""

    NONE = "H0"
    FIGURE_TRUST = "H1"  # şekle aşırı güvenme
    DEFINITION_MIX = "H2"  # tanım karıştırma
    MISSING_PRECOND = "H3"  # teoremi ön koşulsuz uygulama


class PredicateKind(str, Enum):
    """Ön koşulların denetlendiği yüklem tipleri.

    Her yüklem yalnızca `figure` bloğuna bakarak değerlendirilir.
    `rendering` bloğuna erişim YASAKTIR — çizim bağlayıcı değildir.
    """

    RIGHT_ANGLE = "right_angle"  # figure.perpendicular içinde köşe var mı
    CONGRUENT_SIDES = "congruent_sides"  # figure.congruent_segments içinde çift var mı
    SEGMENT_TYPE = "segment_type"  # segment.type beklenen tiple uyuşuyor mu
    SIMILAR = "similar"  # figure.similar içinde çift var mı
    KNOWN_LENGTHS = "known_lengths"  # gerekli uzunluklar verilmiş mi
    REMOTE_ANGLES = "remote_angles"  # dış açı için doğru iç açı çifti mi


@dataclass(frozen=True)
class Precondition:
    """Bir teoremin uygulanabilmesi için sağlanması gereken tek bir koşul.

    `on_violation` alanı, koşul sağlanmadığında **varsayılan** hata sınıfını verir.
    Doğrulayıcı bunu tek durumda geçersiz kılar: öğrenci eksik koşulu ayrı bir
    adımda `rule="verilen"` diyerek iddia etmişse sınıf H1'e çekilir
    (docs/taksonomi.md §4.2).
    """

    kind: PredicateKind
    params: tuple[str, ...]
    on_violation: ErrorClass
    message: str


@dataclass(frozen=True)
class Theorem:
    id: str
    name_tr: str
    preconditions: tuple[Precondition, ...]
    produces: str
    families: tuple[str, ...]  # hangi problem ailelerinde kullanılır
    note: str = ""


# --------------------------------------------------------------------------
# P1 — Üçgende açı hesabı
# --------------------------------------------------------------------------

IC_ACILAR_TOPLAMI = Theorem(
    id="ic_acilar_toplami",
    name_tr="Üçgenin iç açıları toplamı 180°'dir",
    preconditions=(),  # her üçgende geçerli, ön koşul yok
    produces="angle",
    families=("P1", "P2"),
    note="Koşulsuz geçerli olduğu için H3 üretmez; H1/H2 zincirinde ara adım olarak kullanılır.",
)

DIS_ACI = Theorem(
    id="dis_aci",
    name_tr="Dış açı, kendisine komşu olmayan iki iç açının toplamına eşittir",
    preconditions=(
        Precondition(
            kind=PredicateKind.REMOTE_ANGLES,
            params=("exterior_vertex", "remote_a", "remote_b"),
            on_violation=ErrorClass.MISSING_PRECOND,
            message=(
                "Dış açı, kendisine KOMŞU OLMAYAN iki iç açının toplamına eşittir. "
                "Kullanılan açı çifti yanlış."
            ),
        ),
    ),
    produces="angle",
    families=("P1",),
)


# --------------------------------------------------------------------------
# P2 — İkizkenar / eşkenar üçgen
# --------------------------------------------------------------------------

IKIZKENAR_TABAN = Theorem(
    id="ikizkenar_taban",
    name_tr="İkizkenar üçgende taban açıları eştir",
    preconditions=(
        Precondition(
            kind=PredicateKind.CONGRUENT_SIDES,
            params=("side_a", "side_b"),
            on_violation=ErrorClass.MISSING_PRECOND,
            message=(
                "Taban açılarının eşitliği için üçgenin İKİZKENAR olması gerekir. "
                "Verilenlerde eş kenar çifti yok."
            ),
        ),
    ),
    produces="angle",
    families=("P2",),
)


# --------------------------------------------------------------------------
# P3 — Dik üçgende uzunluk
# --------------------------------------------------------------------------

PISAGOR = Theorem(
    id="pisagor",
    name_tr="Pisagor teoremi",
    preconditions=(
        Precondition(
            kind=PredicateKind.RIGHT_ANGLE,
            params=("vertex",),
            on_violation=ErrorClass.MISSING_PRECOND,
            message=(
                "Pisagor teoremi yalnızca DİK üçgende geçerlidir. "
                "Verilenlerde dik açı yok."
            ),
        ),
        Precondition(
            kind=PredicateKind.KNOWN_LENGTHS,
            params=("side_a", "side_b"),
            on_violation=ErrorClass.MISSING_PRECOND,
            message="Pisagor için iki kenar uzunluğu bilinmelidir.",
        ),
    ),
    produces="length",
    families=("P3",),
    note="H1'in kanonik teoremi: öğrenci dikliği çizimden varsayıp buraya gelir.",
)


# --------------------------------------------------------------------------
# P4 — Üçgen eşitsizliği
# --------------------------------------------------------------------------

UCGEN_ESITSIZLIGI = Theorem(
    id="ucgen_esitsizligi",
    name_tr="Bir kenar, diğer ikisinin farkı ile toplamı arasındadır",
    preconditions=(
        Precondition(
            kind=PredicateKind.KNOWN_LENGTHS,
            params=("side_a", "side_b"),
            on_violation=ErrorClass.MISSING_PRECOND,
            message="Üçgen eşitsizliği için diğer iki kenar bilinmelidir.",
        ),
    ),
    produces="range",
    families=("P4",),
)


# --------------------------------------------------------------------------
# P5 — Yardımcı elemanlar
# --------------------------------------------------------------------------

YUKSEKLIK = Theorem(
    id="yukseklik",
    name_tr="Yükseklik, indirildiği kenara diktir",
    preconditions=(
        Precondition(
            kind=PredicateKind.SEGMENT_TYPE,
            params=("segment", "altitude"),
            on_violation=ErrorClass.DEFINITION_MIX,
            message=(
                "Bu doğru parçası yükseklik değildir. "
                "Yükseklik / kenarortay / açıortay karıştırılmış."
            ),
        ),
    ),
    produces="angle",
    families=("P5",),
)

KENARORTAY = Theorem(
    id="kenarortay",
    name_tr="Kenarortay, indirildiği kenarı iki eş parçaya böler",
    preconditions=(
        Precondition(
            kind=PredicateKind.SEGMENT_TYPE,
            params=("segment", "median"),
            on_violation=ErrorClass.DEFINITION_MIX,
            message=(
                "Bu doğru parçası kenarortay değildir. "
                "Kenarı ikiye bölme özelliği yalnızca kenarortaya aittir."
            ),
        ),
    ),
    produces="length",
    families=("P5",),
    note="H2'nin kanonik teoremi: yükseklik ayağı H ile orta nokta M karıştırılır.",
)

ACIORTAY = Theorem(
    id="aciortay",
    name_tr="Açıortay, ait olduğu açıyı iki eş açıya böler",
    preconditions=(
        Precondition(
            kind=PredicateKind.SEGMENT_TYPE,
            params=("segment", "bisector"),
            on_violation=ErrorClass.DEFINITION_MIX,
            message=(
                "Bu doğru parçası açıortay değildir. "
                "Açıyı ikiye bölme özelliği yalnızca açıortaya aittir."
            ),
        ),
    ),
    produces="angle",
    families=("P5",),
)


# --------------------------------------------------------------------------
# P6 — Benzerlik
# --------------------------------------------------------------------------

BENZERLIK_ORANI = Theorem(
    id="benzerlik_orani",
    name_tr="Benzer üçgenlerde karşılıklı kenarlar orantılıdır",
    preconditions=(
        Precondition(
            kind=PredicateKind.SIMILAR,
            params=("triangle_a", "triangle_b"),
            on_violation=ErrorClass.MISSING_PRECOND,
            message="Orantı kurabilmek için üçgenlerin BENZER olduğu verilmelidir.",
        ),
    ),
    produces="length",
    families=("P6",),
    note="H3: oran eşlik gibi kullanılır (k=1 varsayılır). H2: kenarlar yanlış eşleştirilir.",
)


# --------------------------------------------------------------------------
# Kütüphane
# --------------------------------------------------------------------------

THEOREMS: dict[str, Theorem] = {
    t.id: t
    for t in (
        IC_ACILAR_TOPLAMI,
        DIS_ACI,
        IKIZKENAR_TABAN,
        PISAGOR,
        UCGEN_ESITSIZLIGI,
        YUKSEKLIK,
        KENARORTAY,
        ACIORTAY,
        BENZERLIK_ORANI,
    )
}

#: `steps[].rule` alanında teorem id'si yerine kullanılabilen özel değer.
#: Öğrencinin bir bilgiyi "verilen" diye iddia ettiğini gösterir; H1'in işaretidir.
GIVEN = "verilen"


def get(rule_id: str) -> Theorem | None:
    """Teoremi id ile getirir. Bilinmeyen kural için None döner."""
    return THEOREMS.get(rule_id)


def theorems_for_family(family: str) -> list[Theorem]:
    """Bir problem ailesinde kullanılabilecek teoremler."""
    return [t for t in THEOREMS.values() if family in t.families]
