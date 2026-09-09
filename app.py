"""Streamlit demosu.

Amacı staj sunumunda ve danışman görüşmesinde sistemi canlı göstermektir;
ürünleşmiş bir uygulama hedeflenmemektedir.

Anlatının iki can alıcı anı:

  1. Aynı problem, iki farklı yanılgı → sistem ikisini FARKLI teşhis eder ve
     farklı adımı işaretler. "Neden nihai cevaba bakmak yetmez" sorusunun cevabı.
  2. Aynı verilenler, iki farklı çizim → yanıltıcı çizimde izleyici dik açı
     varsayar. H1 sınıfının varlık sebebi tek bakışta görülür.

Çalıştırma:
    streamlit run app.py
"""

from __future__ import annotations

import copy
import random
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import generator as gen  # noqa: E402
import renderer  # noqa: E402
import theorems  # noqa: E402
import verifier as vf  # noqa: E402
import visualize as viz  # noqa: E402

SINIF_ADI = {
    "H0": "Hatasız",
    "H1": "Şekle Aşırı Güvenme",
    "H2": "Tanım Karıştırma",
    "H3": "Teoremi Ön Koşulsuz Uygulama",
}

KURAL_SECENEKLERI = ["verilen", *sorted(theorems.THEOREMS)]

st.set_page_config(page_title="Geometrik Akıl Yürütme Hata Analizi", layout="wide")


@st.cache_data
def ornekleri_yukle(n: int = 400):
    return gen.generate(total=n, seed=20260906)


def sekli_goster(solution: dict, baslik: str | None = None) -> None:
    if baslik:
        st.caption(baslik)
    svg = renderer.to_svg(
        solution["figure"],
        solution["rendering"]["coords"],
        solution["rendering"].get("note", "Şekil ölçekli değildir."),
    )
    st.image(svg, use_container_width=False)


def verilenleri_goster(figure: dict) -> None:
    satirlar = []
    for seg in figure.get("segments", []):
        tip = {"altitude": "yükseklik", "median": "kenarortay", "bisector": "açıortay"}.get(
            seg["type"]
        )
        if tip:
            satirlar.append(f"[{seg['from']}{seg['to']}] {tip}tir")
        if seg.get("length") is not None:
            satirlar.append(f"|{seg['from']}{seg['to']}| = {seg['length']}")
    for aci in figure.get("angles", []):
        if aci.get("value") is not None:
            satirlar.append(f"m({aci['vertex']}) = {aci['value']}°")
    for k in figure.get("perpendicular", []):
        satirlar.append(f"{k} köşesinde dik açı")
    for c in figure.get("congruent_segments", []):
        satirlar.append(f"|{c[0]}| = |{c[1]}|")
    for c in figure.get("similar", []):
        satirlar.append(f"{c[0]} ~ {c[1]}")

    st.markdown("**Verilenler**")
    st.markdown("\n".join(f"- {s}" for s in satirlar) or "- (verilen yok)")

    eksikler = []
    if not figure.get("perpendicular"):
        eksikler.append("diklik")
    if not figure.get("congruent_segments"):
        eksikler.append("kenar eşliği")
    if eksikler:
        st.caption(f"Verilmeyen: {', '.join(eksikler)} — çizimde öyle görünse de.")


def sonucu_goster(bulgu: vf.Finding) -> None:
    if bulgu.is_clean:
        st.success(f"**H0 — {SINIF_ADI['H0']}**\n\n{bulgu.reason}")
        return

    st.error(
        f"**{bulgu.error_class} — {SINIF_ADI[bulgu.error_class]}**\n\n"
        f"Hatalı adım: **{bulgu.error_step}**\n\n{bulgu.reason}"
    )


# --------------------------------------------------------------------------

st.title("Geometrik Akıl Yürütme Hata Analizi")
st.caption(
    "Üçgen geometrisinde öğrenci çözümlerini iki graf olarak modelleyip hatayı "
    "adım düzeyinde konumlandırır."
)

sekme1, sekme2, sekme3 = st.tabs(
    ["Çözüm analizi", "Aynı problem, iki yanılgı", "Çizim nasıl yanıltır?"]
)


# --------------------------------------------------------------------------
# 1) Çözüm analizi — adımlar düzenlenebilir
# --------------------------------------------------------------------------

with sekme1:
    ornekler = ornekleri_yukle()

    ust = st.columns([2, 1, 1])
    with ust[0]:
        aile = st.selectbox(
            "Problem ailesi",
            ["hepsi", "P1", "P2", "P3", "P4", "P5", "P6"],
            help="P1 açı · P2 ikizkenar · P3 dik üçgen · P4 eşitsizlik · "
            "P5 yardımcı elemanlar · P6 benzerlik",
        )
    havuz = [s for s in ornekler if aile == "hepsi" or s["family"] == aile]

    with ust[1]:
        sinif_f = st.selectbox("Beklenen sınıf", ["hepsi", "H0", "H1", "H2", "H3"])
    if sinif_f != "hepsi":
        havuz = [s for s in havuz if s["label"]["error_class"] == sinif_f]

    if not havuz:
        st.warning("Bu filtreyle örnek yok.")
        st.stop()

    with ust[2]:
        idx = st.number_input("Örnek", 0, len(havuz) - 1, 0, help=f"{len(havuz)} örnek")

    secilen = havuz[int(idx)]
    anahtar = secilen["problem_id"] + str(idx) + aile + sinif_f
    if st.session_state.get("_anahtar") != anahtar:
        st.session_state["_anahtar"] = anahtar
        st.session_state["adimlar"] = copy.deepcopy(secilen["steps"])

    sol, sag = st.columns([1, 1])

    with sol:
        st.subheader("Problem")
        st.info(secilen["soru"])
        sekli_goster(secilen)
        verilenleri_goster(secilen["figure"])

        st.subheader("Çözüm adımları")
        st.caption("Gerekçeyi değiştirip sistemin teşhisinin nasıl değiştiğini görebilirsin.")

        for i, adim in enumerate(st.session_state["adimlar"]):
            c1, c2 = st.columns([3, 2])
            with c1:
                st.text_input(
                    f"{adim['id']} — iddia", adim["claim"], key=f"claim_{i}", disabled=True
                )
            with c2:
                yeni = st.selectbox(
                    "gerekçe",
                    KURAL_SECENEKLERI,
                    index=KURAL_SECENEKLERI.index(adim["rule"])
                    if adim["rule"] in KURAL_SECENEKLERI
                    else 0,
                    key=f"rule_{i}",
                )
                st.session_state["adimlar"][i]["rule"] = yeni

    with sag:
        st.subheader("Analiz")
        bulgu = vf.verify(secilen["figure"], st.session_state["adimlar"])
        sonucu_goster(bulgu)

        st.markdown("**Akıl yürütme grafı**")
        st.image(
            viz.reasoning_graph_svg(st.session_state["adimlar"], bulgu.error_step),
            use_container_width=False,
        )
        st.markdown(viz.legend_html(), unsafe_allow_html=True)

        with st.expander("Üretecin etiketi (yalnızca doğrulama için)"):
            etiket = secilen["label"]
            st.write(
                f"Sınıf: `{etiket['error_class']}` · "
                f"Adım: `{etiket['error_step']}` · "
                f"Çizim: `{secilen['rendering']['bias']}`"
            )
            st.caption(
                "Bu bilgi doğrulayıcıya verilmez; yalnızca demoda karşılaştırma için "
                "gösterilir."
            )


# --------------------------------------------------------------------------
# 2) Aynı problem, iki yanılgı
# --------------------------------------------------------------------------

with sekme2:
    st.subheader("Neden nihai cevaba bakmak yetmez?")
    st.markdown(
        "Aşağıdaki iki çözüm **aynı probleme** ait ve ikisi de yanlış. Ama "
        "yanılgılar farklı, dolayısıyla öğretmenin müdahalesi de farklı olmalı. "
        "Sistem ikisini farklı teşhis eder ve **farklı adımı** işaretler."
    )

    ornekler = ornekleri_yukle()
    ciftler = {}
    for s in ornekler:
        if s["label"]["error_class"] in ("H1", "H3"):
            ciftler.setdefault(s["family"], {}).setdefault(
                s["label"]["error_class"], s
            )
    uygun = [f for f, d in ciftler.items() if len(d) == 2]

    if not uygun:
        st.warning("Uygun çift bulunamadı.")
    else:
        aile2 = st.selectbox("Problem ailesi", uygun, key="cift_aile")
        kolonlar = st.columns(2)
        for kol, sinif in zip(kolonlar, ("H1", "H3")):
            ornek = ciftler[aile2][sinif]
            with kol:
                st.markdown(f"#### {sinif} — {SINIF_ADI[sinif]}")
                st.info(ornek["soru"])
                sekli_goster(ornek)
                for adim in ornek["steps"]:
                    st.markdown(f"`{adim['id']}` {adim['claim']} — *{adim['rule']}*")
                bulgu = vf.verify(ornek["figure"], ornek["steps"])
                sonucu_goster(bulgu)
                st.image(
                    viz.reasoning_graph_svg(ornek["steps"], bulgu.error_step, width=280),
                    use_container_width=False,
                )

        st.info(
            "**Ayrım kuralı:** Öğrenci eksik koşulu ayrı bir adımda *verilen* diye "
            "iddia ettiyse H1, hiç anmadan teoremi uyguladıysa H3. Aynı eksik "
            "verilen, iki farklı yanılgı."
        )


# --------------------------------------------------------------------------
# 3) Çizim nasıl yanıltır?
# --------------------------------------------------------------------------

with sekme3:
    st.subheader("Ders kitabı şekilleri ölçekli değildir")
    st.markdown(
        "Aşağıdaki iki çizimin **verilenleri birebir aynı** ve hiçbiri yalan "
        "söylemiyor — çünkü o açı zaten *verilmemiş*. Fark yalnızca verilmemiş "
        "niceliğin nasıl seçildiğinde."
    )

    ornekler = ornekleri_yukle()
    adaylar = [
        s
        for s in ornekler
        if s["label"]["error_class"] == "H1" and s["rendering"]["bias"] == "misleading"
    ]

    def tuzak_metni(solution: dict) -> tuple[str, str]:
        """Tuzağı örnekten okur.

        Metin sabit yazılamaz: bazı örneklerde tuzak diklik, bazılarında kenar
        eşliğidir. Yanlış metin, doğru çizimin anlatısını bozar.
        """
        adim = next((a for a in solution["steps"] if a["rule"] == "verilen"), None)
        refs = (adim or {}).get("refs", {})

        if refs.get("asserts") == "perpendicular":
            k = refs.get("vertex", "?")
            return f"{k} köşesinin dik olup olmadığını", "dik açı"
        if refs.get("asserts") == "congruent_segments":
            a, b = refs.get("segments", ["?", "?"])
            return f"|{a}| ile |{b}| kenarlarının eşit olup olmadığını", "eşit kenar"
        if refs.get("asserts") == "length":
            return f"{refs.get('segment', '?')} uzunluğunun verilip verilmediğini", "verilen uzunluk"
        return "şekilden ne okunabileceğini", "verilmemiş bir ilişki"

    if not adaylar:
        st.warning("Uygun örnek bulunamadı.")
    else:
        tuzak_turleri = {tuzak_metni(s)[1] for s in adaylar}
        tur = st.selectbox("Tuzak türü", sorted(tuzak_turleri), key="tuzak_tur")
        aday = next(s for s in adaylar if tuzak_metni(s)[1] == tur)
        soru_metni, tuzak_adi = tuzak_metni(aday)

        notr = copy.deepcopy(aday)
        notr["rendering"]["coords"] = renderer.layout(
            notr["figure"], "neutral", None, random.Random(7)
        )

        k1, k2 = st.columns(2)
        with k1:
            st.markdown("#### Yanıltıcı çizim")
            sekli_goster(aday)
            st.error(f"İzleyicilerin çoğu burada **{tuzak_adi}** olduğunu söyler.")
        with k2:
            st.markdown("#### Nötr çizim")
            sekli_goster(notr)
            st.success(f"Burada kimse {tuzak_adi} varsaymaz.")

        st.info(
            f"**Sunum önerisi:** Soldaki şekli göster ve dinleyicilere "
            f"**{soru_metni}** sor. Çoğunluk *evet* der. Sonra verilenler listesini "
            f"aç — o bilgi yok. H1 sınıfının varlık sebebi budur."
        )
        verilenleri_goster(aday["figure"])

        st.markdown("**Öğrencinin çözümü**")
        for adim in aday["steps"]:
            st.markdown(f"`{adim['id']}` {adim['claim']} — *{adim['rule']}*")
        sonucu_goster(vf.verify(aday["figure"], aday["steps"]))
