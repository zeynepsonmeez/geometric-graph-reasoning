"""Öğrenciye yönelik yapılandırılmış geri bildirim.

Doğrulayıcı hatanın **nerede** olduğunu söyler; bu modül **niçin** olduğunu ve
**ne yapılması gerektiğini** söyler. İkisi bilinçli olarak ayrıdır:

  - `verifier.py` bir karar verir (sınıf + adım). Deneyde altın standart odur.
  - `feedback.py` o karardan metin üretir. Deneye girmez, öğrenciye gider.

Geri bildirim dört parçadan oluşur:

    ne_yaptin      öğrencinin adımda yaptığı iş, kendi diliyle
    neden_gecersiz kuralın neden çiğnendiği
    eksik_olan     adımın GEÇERLİ olması için neyin verilmiş olması gerektiği
    oneri          genellenebilir ders

`eksik_olan` hesaplanabilir bir alandır: sağlanmayan ön koşul, neyin eksik
olduğunu zaten tam olarak söyler. "Yanlış" demek yerine eksiği adıyla göstermek,
geri bildirimi düzeltilebilir kılar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import turkce
from theorems import GIVEN, THEOREMS, PredicateKind, get

#: Adım kimliğini okunur sıraya çevirmek için.
SIRA_ADI = {1: "1.", 2: "2.", 3: "3.", 4: "4.", 5: "5."}

ELEMAN_ADI = {
    "altitude": "yükseklik",
    "median": "kenarortay",
    "bisector": "açıortay",
    "side": "kenar",
}

ASSERT_ADI = {
    "perpendicular": "dik açı",
    "congruent_segments": "kenar eşitliği",
    "similar": "benzerlik",
    "length": "uzunluk",
    "angle": "açı ölçüsü",
}

#: Her sınıf için genellenebilir ders. Tek tek vakalara değil, alışkanlığa yöneliktir.
DERS = {
    "H1": (
        "Çözüme yalnızca verilenler listesindeki bilgilerle başla. Şekiller "
        "ölçekli değildir: bir açının dik görünmesi, iki kenarın eşit görünmesi "
        "ya da bir üçgenin ikizkenar görünmesi o bilgiyi vermez."
    ),
    # H2 iki farklı biçimde ortaya çıkar ve dersleri aynı değildir.
    "H2_eleman": (
        "Yükseklik dik iner, kenarortay kenarı iki eş parçaya böler, açıortay "
        "açıyı iki eş açıya böler. Bu üçü yalnızca özel durumlarda çakışır; "
        "birinin özelliğini diğerine uygulayamazsın."
    ),
    "H2_eslestirme": (
        "Benzerlik ifadesini yazarken köşe sırası rastgele değildir: ABC ~ DEF "
        "demek A↔D, B↔E, C↔F demektir. Orantı kurmadan önce hangi kenarın "
        "hangisiyle karşılıklı olduğunu bu sıradan oku."
    ),
    "H3": (
        "Bir teoremi uygulamadan önce ön koşulunun verilenlerde sağlandığını "
        "denetle. Teoremi doğru bilmek, onu her üçgende kullanabileceğin "
        "anlamına gelmez."
    ),
}


@dataclass(frozen=True)
class Feedback:
    baslik: str
    ne_yaptin: str
    neden_gecersiz: str
    eksik_olan: str
    oneri: str
    nasil: str = ""
    kirlenmis: tuple[str, ...] = ()

    def as_markdown(self) -> str:
        satirlar = [f"**{self.baslik}**", "", f"**Ne yaptın?** {self.ne_yaptin}"]
        # Hatasız çözümde "neden geçersiz" diye bir şey yoktur; boş bölüm basmak
        # geri bildirimi anlamsız gösterir.
        for etiket, deger in (
            ("Neden geçersiz?", self.neden_gecersiz),
            ("Eksik olan:", self.eksik_olan),
            ("Nasıl ilerlemeliydin?", self.nasil),
        ):
            if deger and deger != "—":
                satirlar += ["", f"**{etiket}** {deger}"]
        satirlar += ["", f"**Ders:** {self.oneri}"]
        if self.kirlenmis:
            satirlar += [
                "",
                f"_{', '.join(self.kirlenmis)} adımları bu hataya dayandığı için "
                f"sonuçları güvenilir değil; ayrıca hata sayılmazlar._",
            ]
        return "\n".join(satirlar)


# --------------------------------------------------------------------------


def _sira(steps: list[dict[str, Any]], adim_id: str | None) -> str:
    for i, st in enumerate(steps, start=1):
        if st["id"] == adim_id:
            return SIRA_ADI.get(i, f"{i}.")
    return "?"


def _kirlenmisler(steps: list[dict[str, Any]], adim_id: str | None) -> tuple[str, ...]:
    if not adim_id:
        return ()
    kirli = {adim_id}
    for _ in range(len(steps)):
        for st in steps:
            if set(st.get("depends_on") or []) & kirli:
                kirli.add(st["id"])
    return tuple(sorted(kirli - {adim_id}))


def _kural_adlari(ids: list[str]) -> str:
    adlar = [t.name_tr for i in ids if (t := get(i))]
    return ", ".join(f"**{a}**" for a in adlar) if adlar else ""


def _tipe_uyan_kurallar(tip: str) -> list[str]:
    """Şekildeki elemanın tipine gerçekten uyan teoremler.

    H2'de "hangi kuralı kullanmalıydın" sorusunun cevabı budur: parça bir
    yükseklikse, yükseklik ön koşulu isteyen teoremler uygulanabilir.
    """
    return [
        t.id
        for t in THEOREMS.values()
        if any(
            p.kind is PredicateKind.SEGMENT_TYPE
            and len(p.params) > 1
            and p.params[1] == tip
            for p in t.preconditions
        )
    ]


def _yetmiyor_notu(uygulanabilir: list[str]) -> str:
    """Kalan kurallar soruyu çözmeye yetmiyorsa bunu söylemek dürüstlüktür."""
    if len(uygulanabilir) <= 1:
        return (
            " Verilenlerin şu hâliyle çözüme götürecek başka bir kural yok; "
            "soru eksik verilmiş olabilir."
        )
    return ""


def _segment_tipi(figure: dict[str, Any], ad: str | None) -> str | None:
    if not ad:
        return None
    for seg in figure.get("segments") or []:
        if sorted(seg["from"] + seg["to"]) == sorted(ad):
            return seg.get("type")
    return None


# --------------------------------------------------------------------------


def _h1(figure, steps, adim, refs, uygulanabilir) -> Feedback:
    """Öğrenci, verilmemiş bir bilgiyi 'verilen' saymış."""
    tur = refs.get("asserts")
    sira = _sira(steps, adim["id"])

    if tur == "perpendicular":
        kose = refs.get("vertex", "?")
        ne = f"{sira} adımda {kose} köşesinde dik açı olduğunu 'verilen' olarak kullandın."
        eksik = f"Soruda **m({kose}) = 90°** verilmiş olsaydı bu adım geçerli olurdu."
    elif tur == "congruent_segments":
        a, b = refs.get("segments", ["?", "?"])
        ne = f"{sira} adımda |{a}| = |{b}| eşitliğini 'verilen' olarak kullandın."
        eksik = f"Soruda **|{a}| = |{b}|** verilmiş olsaydı bu adım geçerli olurdu."
    elif tur == "length":
        seg = refs.get("segment", "?")
        ne = f"{sira} adımda |{seg}| uzunluğunu 'verilen' olarak kullandın."
        eksik = f"Soruda **|{seg}|** uzunluğu verilmiş olsaydı bu adım geçerli olurdu."
    elif tur == "similar":
        ne = f"{sira} adımda üçgenlerin benzer olduğunu 'verilen' olarak kullandın."
        eksik = "Soruda üçgenlerin **benzer olduğu** verilmiş olsaydı bu adım geçerli olurdu."
    else:
        ad = ASSERT_ADI.get(tur, "bir bilgiyi")
        ne = f"{sira} adımda {ad} bilgisini 'verilen' olarak kullandın."
        eksik = "Bu bilgi soruda verilmiş olsaydı adım geçerli olurdu."

    return Feedback(
        baslik="Şekilde gördüğünü verilen sandın",
        ne_yaptin=ne,
        neden_gecersiz=(
            "Bu bilgi verilenler listesinde yok. Şekilde öyle görünmesi onu "
            "verilen yapmaz — şekiller ölçekli değildir."
        ),
        eksik_olan=eksik,
        oneri=DERS["H1"],
        nasil=(
            "Bu bilgi verilmediğine göre ondan yararlanamazsın. Verilenlerin "
            f"şu hâliyle uygulanabilecek kurallar: {_kural_adlari(uygulanabilir)}."
            + _yetmiyor_notu(uygulanabilir)
        ),
        kirlenmis=_kirlenmisler(steps, adim["id"]),
    )


def _h2(figure, steps, adim, refs, theorem, uygulanabilir) -> Feedback:
    """Kullanılan teoremin gerektirdiği eleman tipi tutmuyor."""
    sira = _sira(steps, adim["id"])
    seg = refs.get("segment")
    gercek = _segment_tipi(figure, seg)

    beklenen = next(
        (
            p.params[1]
            for p in theorem.preconditions
            if p.kind.value == "segment_type" and len(p.params) > 1
        ),
        None,
    )

    ders_anahtari = "H2_eleman" if (seg and gercek and beklenen) else "H2_eslestirme"

    if seg and gercek and beklenen:
        ne = (
            f"{sira} adımda [{seg}] doğru parçasına "
            f"**{ELEMAN_ADI.get(beklenen, beklenen)}** özelliğini uyguladın."
        )
        neden = (
            f"[{seg}] bir **{ELEMAN_ADI.get(gercek, gercek)}**"
            f"{turkce.ek_dir(ELEMAN_ADI.get(gercek, gercek))}, "
            f"{ELEMAN_ADI.get(beklenen, beklenen)} değil. "
            f"{theorem.name_tr}."
        )
        eksik = (
            f"Bu adımın geçerli olması için [{seg}] parçasının "
            f"**{ELEMAN_ADI.get(beklenen, beklenen)}** olması gerekirdi."
        )
        # Şekildeki parça hangi tipteyse, ona uyan kural kullanılmalıydı.
        uyanlar = _tipe_uyan_kurallar(gercek)
        nasil = (
            f"[{seg}] bir {ELEMAN_ADI.get(gercek, gercek)} olduğuna göre "
            f"{_kural_adlari(uyanlar)} kuralını kullanmalıydın."
            if uyanlar
            else f"[{seg}] parçasının tipine uygun bir kural seçmelisin."
        )
    else:
        ne = f"{sira} adımda karşılıklı elemanları yanlış eşleştirdin."
        neden = (
            "Benzerlik ifadesindeki köşe sırası karşılıklı kenarları belirler: "
            "ABC ~ DEF ise A↔D, B↔E, C↔F."
        )
        eksik = "Eşlemenin köşe sırasına uygun yapılması gerekirdi."
        benzer = (figure.get("similar") or [[None, None]])[0]
        nasil = (
            f"Benzerlik ifadesi {benzer[0]} ~ {benzer[1]} olduğuna göre karşılıklı "
            f"köşeleri baştan eşle, orantıyı ondan sonra kur."
            if benzer[0]
            else "Karşılıklı kenarları benzerlik ifadesindeki köşe sırasından oku."
        )

    return Feedback(
        baslik="Kavramları birbirine karıştırdın",
        ne_yaptin=ne,
        neden_gecersiz=neden,
        eksik_olan=eksik,
        oneri=DERS[ders_anahtari],
        nasil=nasil,
        kirlenmis=_kirlenmisler(steps, adim["id"]),
    )


def _h3(figure, steps, adim, theorem, mesaj, uygulanabilir) -> Feedback:
    """Teorem doğru, ön koşulu sağlanmıyor."""
    sira = _sira(steps, adim["id"])
    ad = theorem.name_tr if theorem else adim.get("rule", "bir teorem")

    # Doğrulayıcının mesajı "<teorem adı>: <gerekçe>" biçimindedir; teorem adı
    # zaten "ne yaptın" satırında geçtiği için baştaki tekrar atılır.
    if theorem and mesaj.startswith(theorem.name_tr):
        mesaj = mesaj[len(theorem.name_tr):].lstrip(": ").strip() or mesaj

    return Feedback(
        baslik="Teoremi koşulu sağlanmadan uyguladın",
        ne_yaptin=f"{sira} adımda **{ad}** kuralını uyguladın.",
        neden_gecersiz=mesaj,
        eksik_olan=(
            "Teoremin ön koşulunun verilenlerde sağlanması gerekirdi; "
            "sağlanmadığı için bu adımdan çıkan sonuç geçersizdir."
        ),
        nasil=(
            "Verilenlerin şu hâliyle uygulanabilecek kurallar: "
            f"{_kural_adlari(uygulanabilir)}."
            + _yetmiyor_notu(uygulanabilir)
        ),
        oneri=DERS["H3"],
        kirlenmis=_kirlenmisler(steps, adim["id"]),
    )


TEMIZ = Feedback(
    baslik="Çözüm geçerli",
    ne_yaptin="Her adımda kullandığın kuralın ön koşulu verilenlerde sağlanıyor.",
    neden_gecersiz="—",
    eksik_olan="—",
    oneri=(
        "Verilenlerle sınırlı kalıp her adımda kuralın koşulunu denetlemek "
        "doğru alışkanlıktır."
    ),
)


def explain(
    figure: dict[str, Any],
    steps: list[dict[str, Any]],
    error_class: str,
    error_step: str | None,
    reason: str,
    uygulanabilir: list[str] | None = None,
) -> Feedback:
    """Doğrulayıcının kararından öğrenciye yönelik geri bildirim üretir.

    Girdi olarak doğrulayıcının çıktısını alır; kendi başına karar vermez.
    Böylece geri bildirim ile teşhis birbirinden ayrışamaz.
    """
    if error_class == "H0" or error_step is None:
        return TEMIZ

    adim = next((s for s in steps if s["id"] == error_step), None)
    if adim is None:
        return TEMIZ

    refs = adim.get("refs") or {}
    theorem = None if adim.get("rule") == GIVEN else get(adim.get("rule"))

    uygulanabilir = uygulanabilir or []

    if error_class == "H1":
        return _h1(figure, steps, adim, refs, uygulanabilir)
    if error_class == "H2":
        return _h2(figure, steps, adim, refs, theorem, uygulanabilir) if theorem else TEMIZ
    return _h3(figure, steps, adim, theorem, reason, uygulanabilir)


def explain_finding(
    figure: dict[str, Any],
    steps: list[dict[str, Any]],
    finding,
    uygulanabilir: list[str] | None = None,
) -> Feedback:
    """`verifier.Finding` nesnesinden doğrudan geri bildirim üretir.

    `uygulanabilir` listesini çağıran taraf `verifier.applicable_rules()` ile
    hesaplayıp geçirir; bu modül doğrulayıcıyı import etmez.
    """
    return explain(
        figure, steps, finding.error_class, finding.error_step, finding.reason,
        uygulanabilir,
    )
