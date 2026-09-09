"""Sembolik doğrulayıcı.

Bir çözümün adımlarını sırayla denetler ve ilk geçersiz adımı, hata sınıfıyla
birlikte döndürür. Kural tabanlı ve deterministiktir: aynı girdiye her zaman
aynı yanıtı verir.

Rolü iki katlıdır:
  - **Ürünün motoru** — demo arayüzünde öğrenciye gösterilen teşhisi üretir.
  - **Etiketleme oracle'ı** — dil modeli deneyinde altın standarttır.

Ölçüm nesnesi DEĞİLDİR: sentetik veride yüksek skor alması beklenen davranıştır.
Gerçek sınavı elle yazılan kümedir (docs/taksonomi.md §4.5).

DİKKAT — mimari kuralları:
  1. Bu modül `generator.py` ve `renderer.py` modüllerini import ETMEZ.
     Üreteç hatayı KURAR, doğrulayıcı geçerliliği DENETLER. Ortak olan tek şey
     docs/taksonomi.md spesifikasyonudur.
  2. `rendering` bloğuna ERİŞMEZ. `verify()` yalnızca `figure` ve `steps` alır;
     çizim koordinatları imzaya hiç girmez. Çizim bağlayıcı değildir.
  Her ikisi de tests/test_independence.py ile denetlenir.

İddia metinleri AYRIŞTIRILMAZ. Adımın hangi varlıklar hakkında olduğu `refs`
alanından okunur (yapılandırılmış adım girişi).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from theorems import GIVEN, ErrorClass, PredicateKind, Theorem, get

#: `figure` içinde bir ilişkinin tutulduğu alan adları.
ASSERT_FIELDS = {
    "perpendicular": "perpendicular",
    "congruent_segments": "congruent_segments",
    "similar": "similar",
}


@dataclass(frozen=True)
class Finding:
    """Denetim sonucu."""

    error_class: str
    error_step: str | None
    reason: str
    violated: str | None = None

    @property
    def is_clean(self) -> bool:
        return self.error_class == ErrorClass.NONE.value


CLEAN = Finding(ErrorClass.NONE.value, None, "Tüm adımların ön koşulları sağlanıyor.")


# --------------------------------------------------------------------------
# figure sorguları — doğrulayıcının gördüğü tek gerçeklik
# --------------------------------------------------------------------------


def _segments(figure: dict[str, Any]) -> list[dict[str, Any]]:
    return figure.get("segments") or []


def _same_segment(a: str, b: str) -> bool:
    """'AH' ile 'HA' aynı doğru parçasıdır."""
    return sorted(a) == sorted(b)


def _find_segment(figure: dict[str, Any], name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    for seg in _segments(figure):
        if _same_segment(seg["from"] + seg["to"], name):
            return seg
    return None


def _has_right_angle(figure: dict[str, Any], vertex: str | None = None) -> bool:
    perpendicular = figure.get("perpendicular") or []
    return bool(perpendicular) if vertex is None else vertex in perpendicular


def _has_congruent_sides(figure: dict[str, Any], pair: list[str] | None = None) -> bool:
    pairs = figure.get("congruent_segments") or []
    if pair is None:
        return bool(pairs)
    return any(
        {_norm(x) for x in known} == {_norm(x) for x in pair} for known in pairs
    )


def _norm(segment_name: str) -> str:
    return "".join(sorted(segment_name))


def _has_similar(figure: dict[str, Any]) -> bool:
    return bool(figure.get("similar") or [])


def _known_length_count(figure: dict[str, Any]) -> int:
    return sum(1 for seg in _segments(figure) if seg.get("length") is not None)


def _has_segment_of_type(
    figure: dict[str, Any], expected: str, name: str | None = None
) -> bool:
    """Belirtilen tipte bir doğru parçası var mı?

    `name` verilmişse yalnızca o parçanın tipine bakılır — H2'nin özü budur:
    öğrencinin kullandığı parça, teoremin gerektirdiği tipte mi?
    """
    if name:
        seg = _find_segment(figure, name)
        return seg is not None and seg.get("type") == expected
    return any(seg.get("type") == expected for seg in _segments(figure))


def _triangle_vertices(figure: dict[str, Any]) -> set[str]:
    vertices: set[str] = set()
    for seg in _segments(figure):
        if seg.get("type") == "side":
            vertices.update((seg["from"], seg["to"]))
    return vertices


# --------------------------------------------------------------------------
# Ön koşul denetimi
# --------------------------------------------------------------------------


def _check_precondition(
    kind: PredicateKind,
    params: tuple[str, ...],
    figure: dict[str, Any],
    refs: dict[str, Any],
) -> bool:
    if kind is PredicateKind.RIGHT_ANGLE:
        return _has_right_angle(figure, refs.get("vertex"))

    if kind is PredicateKind.CONGRUENT_SIDES:
        return _has_congruent_sides(figure, refs.get("segments"))

    if kind is PredicateKind.SIMILAR:
        return _has_similar(figure)

    if kind is PredicateKind.KNOWN_LENGTHS:
        return _known_length_count(figure) >= 2

    if kind is PredicateKind.SEGMENT_TYPE:
        expected = params[1] if len(params) > 1 else "side"
        return _has_segment_of_type(figure, expected, refs.get("segment"))

    if kind is PredicateKind.REMOTE_ANGLES:
        return _remote_angles_valid(figure, refs)

    # Bilinmeyen yüklem: denetlenemeyeni geçerli sayma, açıkça başarısız et.
    return False


def _remote_angles_valid(figure: dict[str, Any], refs: dict[str, Any]) -> bool:
    """Dış açı, kendisine KOMŞU OLMAYAN iki iç açının toplamıdır.

    Öğrencinin topladığı açı çifti, dış açının bulunduğu köşeyi içeriyorsa
    ya da üçgenin diğer iki köşesinden farklıysa koşul sağlanmaz.
    """
    exterior = refs.get("exterior")
    remote = refs.get("remote")
    if not exterior or not remote:
        return False

    beklenen = _triangle_vertices(figure) - {exterior}
    return set(remote) == beklenen


def _correspondence_valid(figure: dict[str, Any], refs: dict[str, Any]) -> bool:
    """Benzer üçgenlerde karşılıklı kenarlar doğru eşleştirilmiş mi?

    `figure.similar` çifti köşe sırasını belirler: ABC ~ DEF ise A↔D, B↔E, C↔F.
    Öğrencinin `maps` eşlemesi bu sıralamayla tutarlı olmalıdır.
    """
    maps = refs.get("maps")
    if not maps:
        return True  # eşleme iddiası yoksa denetlenecek bir şey de yok

    for first, second in figure.get("similar") or []:
        harita = dict(zip(first, second))
        for kaynak, hedef in maps:
            cevrilmis = {harita.get(ch, ch) for ch in kaynak}
            if cevrilmis != set(hedef):
                return False
    return True


# --------------------------------------------------------------------------
# "verilen" adımlarının denetimi — H1'in özü
# --------------------------------------------------------------------------


def _check_given(figure: dict[str, Any], refs: dict[str, Any]) -> tuple[bool, str]:
    """Öğrencinin "verilen" dediği şey gerçekten verilenler arasında mı?

    docs/taksonomi.md §1 (kapalı dünya): `figure` bloğunda listelenmeyen hiçbir
    ilişki verilmiş sayılmaz. Listede olmayanı "verilen" diye kullanmak H1'dir.
    """
    asserts = refs.get("asserts")

    if asserts == "perpendicular":
        vertex = refs.get("vertex")
        ok = _has_right_angle(figure, vertex)
        return ok, f"{vertex} köşesinde dik açı verilenler arasında yok."

    if asserts == "congruent_segments":
        pair = refs.get("segments")
        ok = _has_congruent_sides(figure, pair)
        adlar = " ile ".join(f"|{p}|" for p in pair) if pair else "kenarların"
        return ok, f"{adlar} eşitliği verilenler arasında yok."

    if asserts == "similar":
        ok = _has_similar(figure)
        return ok, "Üçgenlerin benzerliği verilenler arasında yok."

    if asserts == "length":
        seg = _find_segment(figure, refs.get("segment"))
        ok = seg is not None and seg.get("length") is not None
        return ok, f"{refs.get('segment')} uzunluğu verilenler arasında yok."

    if asserts == "angle":
        vertex = refs.get("vertex")
        ok = any(
            a.get("vertex") == vertex and a.get("value") is not None
            for a in figure.get("angles") or []
        )
        return ok, f"{vertex} açısının ölçüsü verilenler arasında yok."

    # refs.asserts belirtilmemişse iddia denetlenemez; sessizce geçerli sayma.
    return False, "Adımın neyi 'verilen' saydığı belirtilmemiş (refs.asserts eksik)."


# --------------------------------------------------------------------------
# Ana denetim
# --------------------------------------------------------------------------


def _topological(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adımları bağımlılık sırasına göre sıralar.

    Çevrim veya çözülemeyen bağımlılık varsa kalanları özgün sırada ekler;
    biçimsel bozukluk hata sınıfı değildir, denetim yine de yürür.
    """
    kalan = list(steps)
    cozulen: set[str] = set()
    sirali: list[dict[str, Any]] = []

    while kalan:
        hazir = [s for s in kalan if set(s.get("depends_on") or []) <= cozulen]
        if not hazir:
            sirali.extend(kalan)
            break
        for s in hazir:
            sirali.append(s)
            cozulen.add(s["id"])
            kalan.remove(s)

    return sirali


def verify(figure: dict[str, Any], steps: list[dict[str, Any]]) -> Finding:
    """Çözümü denetler ve ilk geçersiz adımı döndürür.

    İmza kasıtlı olarak dar tutulmuştur: tüm çözüm nesnesi değil, yalnızca
    `figure` ve `steps` alınır. Böylece `rendering` bloğuna erişim kod düzeyinde
    imkânsızdır (docs/taksonomi.md §1).
    """
    for step in _topological(steps):
        refs = step.get("refs") or {}
        rule_id = step.get("rule")

        # 1) "verilen" iddiası — kapalı dünya denetimi
        if rule_id == GIVEN:
            ok, mesaj = _check_given(figure, refs)
            if not ok:
                return Finding(
                    ErrorClass.FIGURE_TRUST.value,
                    step["id"],
                    f"{mesaj} Şekilde öyle görünmesi onu verilen yapmaz.",
                    violated="given",
                )
            continue

        theorem: Theorem | None = get(rule_id)
        if theorem is None:
            return Finding(
                ErrorClass.MISSING_PRECOND.value,
                step["id"],
                f"Tanınmayan kural: '{rule_id}'.",
                violated="unknown_rule",
            )

        # 2) Teoremin ön koşulları
        for pre in theorem.preconditions:
            if _check_precondition(pre.kind, pre.params, figure, refs):
                continue
            return Finding(
                pre.on_violation.value,
                step["id"],
                f"{theorem.name_tr}: {pre.message}",
                violated=pre.kind.value,
            )

        # 3) Karşılıklılık denetimi — ön koşullar sağlansa da eşleme yanlış olabilir
        if not _correspondence_valid(figure, refs):
            return Finding(
                ErrorClass.DEFINITION_MIX.value,
                step["id"],
                (
                    f"{theorem.name_tr}: karşılıklı kenarlar yanlış eşleştirilmiş. "
                    f"Benzerlik ifadesindeki köşe sırası eşlemeyi belirler."
                ),
                violated="correspondence",
            )

    return CLEAN


def verify_solution(solution: dict[str, Any]) -> Finding:
    """Çözüm nesnesinden yalnızca izin verilen alanları geçirerek denetler."""
    return verify(solution["figure"], solution["steps"])
