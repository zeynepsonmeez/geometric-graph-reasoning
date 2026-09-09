"""Elle yazılan küme için örnek giriş formu.

Gönüllüler bu formu doldurur. JSON düzenlemeleri gerekmez.

TASARIM KURALI — bu sayfa hata sınıflarını (H0–H3) **göstermez ve sormaz**.
Gönüllü sınıfları bilirse sınıfa göre örnek üretmeye başlar ve küme sentetik
derlemin elle yazılmış kopyasına dönüşür; kümenin tüm değeri bağımsızlığından
gelir (data/handwritten/README.md).

Etiketleme ayrı sayfada, ayrı kişi tarafından yapılır.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import handwritten as hw  # noqa: E402
import renderer  # noqa: E402
import ui  # noqa: E402
import theorems  # noqa: E402

KURALLAR = ["verilen", *sorted(theorems.THEOREMS)]
ASSERT_SECENEKLERI = ["perpendicular", "congruent_segments", "similar", "length", "angle"]
SEGMENT_TIPLERI = ["side", "altitude", "median", "bisector"]

st.set_page_config(page_title="Örnek yaz", layout="wide")
ui.apply_theme()
st.title("Elle yazılan küme — örnek girişi")

st.info(
    "**Yönerge.** Bir üçgen problemi ve bir öğrenci çözümü yaz. Bazı çözümler "
    "**doğru**, bazıları **kasıtlı hatalı** olsun. Hata yaparken gerçek bir "
    "öğrencinin düşebileceği türden bir hata yap: şekle bakıp verilmemiş bir şeyi "
    "varsaymak, kavramları karıştırmak, bir kuralı koşulu sağlanmadan uygulamak.\n\n"
    "**Hangi hatayı yaptığını yazma.** Etiketlemeyi başkası yapacak."
)

with st.expander("Kritik nokta: verilenler listesi"):
    st.markdown(
        "Aşağıda **yalnızca soruda açıkça verilen** bilgileri işaretle. "
        "Çizimde öyle görünmesi bir bilgiyi verilen yapmaz — şekil ölçekli değildir.\n\n"
        "Örneğin dik açı verilmediyse `Dik açı olan köşeler` alanını **boş bırak**, "
        "öğrenci çözümünde onu kullansa bile."
    )

mevcut = {s["problem_id"] for s in hw.load_solutions()}
st.caption(f"Şu an kümede {len(mevcut)} örnek var (hedef: 30).")


# --------------------------------------------------------------------------
# Kimlik ve problem
# --------------------------------------------------------------------------

ust = st.columns([1, 1, 2])
with ust[0]:
    sira = 1
    while f"EL-{sira:04d}" in mevcut:
        sira += 1
    pid = st.text_input("Örnek kimliği", f"EL-{sira:04d}")
with ust[1]:
    aile = st.selectbox(
        "Problem ailesi",
        ["P1", "P2", "P3", "P4", "P5", "P6"],
        help="P1 açı · P2 ikizkenar · P3 dik üçgen · P4 eşitsizlik · "
        "P5 yardımcı elemanlar · P6 benzerlik",
    )
with ust[2]:
    kazanim = st.text_input("Kazanım kodu (isteğe bağlı)", "")

soru = st.text_area(
    "Problem metni",
    placeholder="ABC üçgeninde |AB| = 5 br ve |BC| = 7 br verilmiştir. |AC| kaç birimdir?",
    height=70,
)

st.divider()
sol, sag = st.columns([1, 1])


# --------------------------------------------------------------------------
# Şekil
# --------------------------------------------------------------------------

with sol:
    st.subheader("Şekil")

    koseler_metin = st.text_input("Köşeler (virgülle)", "A, B, C")
    koseler = [k.strip().upper() for k in koseler_metin.split(",") if k.strip()]

    yardimci = st.text_input(
        "Yardımcı nokta (yükseklik/kenarortay/açıortay ayağı, boş bırakılabilir)", ""
    ).strip().upper()
    noktalar = koseler + ([yardimci] if yardimci else [])

    st.markdown("**Kenarlar ve uzunlukları**")
    st.caption("Uzunluğu verilmeyen kenarı boş bırak.")

    segmentler = []
    if len(koseler) >= 3:
        kenar_ciftleri = [
            (koseler[0], koseler[1]),
            (koseler[1], koseler[2]),
            (koseler[0], koseler[2]),
        ]
        for a, b in kenar_ciftleri:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.text_input("kenar", f"[{a}{b}]", disabled=True, key=f"kn_{a}{b}")
            with c2:
                deger = st.text_input("uzunluk", "", key=f"uz_{a}{b}")
            segmentler.append(
                {
                    "from": a,
                    "to": b,
                    "type": "side",
                    "length": float(deger) if deger.strip() else None,
                }
            )

    if yardimci and koseler:
        c1, c2 = st.columns([1, 1])
        with c1:
            tepe = st.selectbox("yardımcı elemanın çıktığı köşe", koseler, key="tepe")
        with c2:
            tip = st.selectbox(
                "türü", ["altitude", "median", "bisector"], key="yrd_tip",
                format_func=lambda t: {
                    "altitude": "yükseklik", "median": "kenarortay", "bisector": "açıortay"
                }[t],
            )
        segmentler.append({"from": tepe, "to": yardimci, "type": tip, "length": None})

    st.markdown("**Verilen açılar**")
    acilar = []
    for k in koseler:
        deger = st.text_input(f"m({k})", "", key=f"ac_{k}")
        acilar.append({"vertex": k, "value": float(deger) if deger.strip() else None})

    dik = st.multiselect(
        "Dik açı olan köşeler", koseler,
        help="Yalnızca soruda AÇIKÇA verilmişse işaretle.",
    )

    es_metin = st.text_input(
        "Eş kenar çifti (örn. AB=AC, boş bırakılabilir)", "",
        help="Yalnızca soruda açıkça verilmişse yaz.",
    )
    es_kenarlar = []
    if "=" in es_metin:
        parcalar = [p.strip().upper() for p in es_metin.split("=")]
        if len(parcalar) == 2 and all(parcalar):
            es_kenarlar = [parcalar]

    benzer_metin = st.text_input("Benzer üçgen çifti (örn. ABC~DEF)", "")
    benzer = []
    if "~" in benzer_metin:
        parcalar = [p.strip().upper() for p in benzer_metin.split("~")]
        if len(parcalar) == 2 and all(parcalar):
            benzer = [parcalar]

    bias = st.radio(
        "Çizim türü",
        ["neutral", "misleading"],
        format_func=lambda b: {
            "neutral": "Nötr — belirgin biçimde genel görünsün",
            "misleading": "Yanıltıcı — verilmemiş bir nicelik özel durum gibi görünsün",
        }[b],
        horizontal=False,
    )


figure = {
    "points": noktalar,
    "segments": segmentler,
    "angles": acilar,
    "perpendicular": dik,
    "congruent_segments": es_kenarlar,
    "similar": benzer,
}


# --------------------------------------------------------------------------
# Adımlar
# --------------------------------------------------------------------------

with sag:
    st.subheader("Öğrencinin çözüm adımları")
    st.caption("Bir adım = bir kural uygulaması. Aritmetik ayrı adım değildir.")

    adim_sayisi = st.number_input("Adım sayısı", 1, 5, 2)
    adimlar = []

    for i in range(int(adim_sayisi)):
        with st.container(border=True):
            st.markdown(f"**Adım s{i + 1}**")
            iddia = st.text_input("İddia", key=f"cl_{i}", placeholder="m(B) = 90")
            kural = st.selectbox("Gerekçe", KURALLAR, key=f"rl_{i}")

            bagimli = st.multiselect(
                "Hangi adımlara dayanıyor?",
                [f"s{j + 1}" for j in range(i)],
                key=f"dp_{i}",
            )

            refs: dict = {}
            if kural == "verilen":
                st.caption("Öğrenci neyi 'verilmiş' sayıyor?")
                asserts = st.selectbox(
                    "tür", ASSERT_SECENEKLERI, key=f"as_{i}",
                    format_func=lambda a: {
                        "perpendicular": "dik açı", "congruent_segments": "kenar eşliği",
                        "similar": "benzerlik", "length": "uzunluk", "angle": "açı ölçüsü",
                    }[a],
                )
                refs["asserts"] = asserts
                if asserts in ("perpendicular", "angle"):
                    refs["vertex"] = st.selectbox("köşe", koseler or ["A"], key=f"vx_{i}")
                elif asserts == "congruent_segments":
                    ç = st.text_input("kenar çifti (örn. AB=AC)", key=f"sg_{i}")
                    if "=" in ç:
                        refs["segments"] = [p.strip().upper() for p in ç.split("=")]
                elif asserts == "length":
                    refs["segment"] = st.text_input(
                        "kenar (örn. BC)", key=f"ln_{i}"
                    ).strip().upper()
            elif kural in ("yukseklik", "kenarortay", "aciortay", "hipotenus_kenarortay"):
                refs["segment"] = st.text_input(
                    "hangi doğru parçası? (örn. AH)", key=f"sm_{i}"
                ).strip().upper()
                if kural == "hipotenus_kenarortay" and koseler:
                    refs["vertex"] = st.selectbox("dik köşe", koseler, key=f"hv_{i}")
            elif kural == "dis_aci" and koseler:
                refs["exterior"] = st.selectbox("dış açının köşesi", koseler, key=f"ex_{i}")
                refs["remote"] = st.multiselect(
                    "toplanan iç açılar", koseler, key=f"rm_{i}", max_selections=2
                )
            elif kural == "benzerlik_orani":
                e = st.text_input(
                    "karşılıklı kenarlar (örn. AB-DE)", key=f"mp_{i}"
                )
                if "-" in e:
                    refs["maps"] = [[p.strip().upper() for p in e.split("-")]]

            adimlar.append(
                {
                    "id": f"s{i + 1}",
                    "claim": iddia,
                    "rule": kural,
                    "depends_on": bagimli,
                    **({"refs": {k: v for k, v in refs.items() if v}} if refs else {}),
                }
            )


# --------------------------------------------------------------------------
# Önizleme ve kaydetme
# --------------------------------------------------------------------------

st.divider()
solution = {
    "problem_id": pid,
    "family": aile,
    "kazanim_kodu": kazanim or None,
    "soru": soru,
    "figure": figure,
    "rendering": {"bias": bias, "note": "Şekil ölçekli değildir."},
    "steps": adimlar,
}

onizleme, denetim = st.columns([1, 1])

with onizleme:
    st.subheader("Şekil önizlemesi")
    try:
        dolu = hw.fill_rendering(solution)
        st.image(
            renderer.to_svg(
                dolu["figure"], dolu["rendering"]["coords"], dolu["rendering"]["note"]
            ),
            use_container_width=False,
        )
    except Exception as e:
        dolu = solution
        st.warning(f"Çizim henüz oluşturulamadı: {e}")

with denetim:
    st.subheader("Denetim")
    sorunlar = hw.check([dolu])
    if sorunlar:
        for s in sorunlar:
            st.warning(s)
    else:
        st.success("Örnek eksiksiz görünüyor.")

    if pid in mevcut:
        st.error(f"`{pid}` zaten var. Kimliği değiştir.")

    kaydedilebilir = not sorunlar and pid not in mevcut
    if st.button("Örneği kaydet", type="primary", disabled=not kaydedilebilir):
        hw.SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
        yol = hw.SOLUTIONS_DIR / f"{pid}.json"
        yol.write_text(
            json.dumps(dolu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        st.success(f"Kaydedildi: `{yol.name}`")
        st.balloons()

with st.expander("Ham JSON"):
    st.json(dolu)
