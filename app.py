"""Streamlit demosu.

Amacı staj sunumunda ve danışman görüşmesinde sistemi canlı göstermektir.

Düzen kararları:
  - Kontroller kenar çubuğunda; ana alan yalnızca içerik gösterir.
  - Sonuç kartı sayfanın en baskın öğesidir — projenin çıktısı "yanlış" değil,
    konumu belli bir teşhistir.
  - Şekiller büyük çizilir; sunumda uzaktan okunabilmeleri gerekir.

Anlatının iki can alıcı anı:
  1. Aynı problem, iki farklı yanılgı → farklı teşhis, farklı adım.
  2. Aynı verilenler, iki farklı çizim → yanıltıcı olanda izleyici tuzağa düşer.

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
import ui  # noqa: E402
import verifier as vf  # noqa: E402
import visualize as viz  # noqa: E402

KURAL_SECENEKLERI = ["verilen", *sorted(theorems.THEOREMS)]
SEKIL_OLCEK = 2.0

st.set_page_config(
    page_title="Geometrik Akıl Yürütme Hata Analizi",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.apply_theme()


@st.cache_data
def ornekleri_yukle(n: int = 600):
    return gen.generate(total=n, seed=20260906)


def verilen_satirlari(figure: dict) -> tuple[list[str], list[str]]:
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

    eksikler = []
    if not figure.get("perpendicular"):
        eksikler.append("diklik")
    if not figure.get("congruent_segments"):
        eksikler.append("kenar eşliği")
    return satirlar, eksikler


def sekli_ciz(solution: dict, olcek: float = SEKIL_OLCEK) -> None:
    ui.sekil(
        renderer.to_svg(
            solution["figure"],
            solution["rendering"]["coords"],
            solution["rendering"].get("note", "Şekil ölçekli değildir."),
            scale=olcek,
        )
    )


# --------------------------------------------------------------------------

ui.baslik(
    "Geometrik Akıl Yürütme Hata Analizi",
    "Üçgen geometrisinde öğrenci çözümlerini iki graf olarak modelleyip hatayı "
    "<b>adım düzeyinde</b> konumlandırır.",
)

sekme1, sekme2, sekme3 = st.tabs(
    ["  Çözüm analizi  ", "  Aynı problem, iki yanılgı  ", "  Çizim nasıl yanıltır?  "]
)


# --------------------------------------------------------------------------
# 1) Çözüm analizi
# --------------------------------------------------------------------------

with sekme1:
    ornekler = ornekleri_yukle()

    with st.sidebar:
        st.markdown("### Örnek seçimi")
        aile = st.selectbox(
            "Problem ailesi",
            ["hepsi", "P1", "P2", "P3", "P4", "P5", "P6"],
            help="P1 açı · P2 ikizkenar · P3 dik üçgen · P4 eşitsizlik · "
            "P5 yardımcı elemanlar · P6 benzerlik",
        )

        aile_havuzu = [s for s in ornekler if aile == "hepsi" or s["family"] == aile]

        # Sınıf seçenekleri seçili aileye göre daraltılır: her aile her sınıfı
        # beslemez (P4'te H2 yoktur). Olmayan kombinasyonu seçtirmek, kullanıcıyı
        # boş ekrana götürür.
        var_olanlar = sorted({s["label"]["error_class"] for s in aile_havuzu})
        sinif_f = st.selectbox("Beklenen sınıf", ["hepsi", *var_olanlar])

        havuz = [
            s
            for s in aile_havuzu
            if sinif_f == "hepsi" or s["label"]["error_class"] == sinif_f
        ]

        idx = st.number_input("Örnek", 0, max(len(havuz) - 1, 0), 0) if havuz else 0
        st.caption(f"{len(havuz)} örnek eşleşti")

        eksik = sorted({"H0", "H1", "H2", "H3"} - set(var_olanlar))
        if eksik and aile != "hepsi":
            st.caption(f"{aile} ailesi şu sınıfları beslemiyor: {', '.join(eksik)}")

        st.divider()
        st.caption(
            "Ana ekrandan adımların **gerekçesini** değiştirip teşhisin nasıl "
            "değiştiğini görebilirsin."
        )

    secilen = havuz[int(idx)] if havuz else None

    if secilen is None:
        # st.stop() KULLANILMAZ: betigi tumuyle durdurur ve diger sekmeler de
        # bosalir. Bos sonuc yalnizca bu sekmeyi etkilemelidir.
        st.warning("Bu filtreyle örnek yok. Kenar çubuğundan filtreleri gevşet.")
    else:
        anahtar = f"{secilen['problem_id']}|{idx}|{aile}|{sinif_f}"
        if st.session_state.get("_anahtar") != anahtar:
            st.session_state["_anahtar"] = anahtar
            st.session_state["adimlar"] = copy.deepcopy(secilen["steps"])

        bulgu = vf.verify(secilen["figure"], st.session_state["adimlar"])

        # Teşhis en üstte, tam genişlikte
        ui.sonuc_karti(bulgu.error_class, bulgu.error_step, bulgu.reason)

        # Çift graf — projenin tezi tek görselde: solda ne verildi, sağda
        # öğrenci nasıl ilerledi, arada tutarsızlığın nerede olduğu.
        ui.sekil(
            viz.dual_graph_svg(
                secilen["figure"],
                renderer.to_svg(
                    secilen["figure"],
                    secilen["rendering"]["coords"],
                    secilen["rendering"].get("note", "Şekil ölçekli değildir."),
                ),
                st.session_state["adimlar"],
                bulgu.error_step,
                bulgu.error_class,
            )
        )
        st.markdown(viz.legend_html(), unsafe_allow_html=True)

        st.write("")
        sol, sag = st.columns([1.15, 1])

        with sol:
            ui.bolum("Problem")
            st.markdown(f"**{secilen['soru']}**")
            st.write("")
            satirlar, eksikler = verilen_satirlari(secilen["figure"])
            ui.verilenler_karti(satirlar, eksikler)

        with sag:
            ui.bolum("Adımların gerekçesini değiştir")
            st.markdown(
                '<div class="altyazi">Bir adımın gerekçesini değiştirdiğinde '
                "teşhis anında yeniden hesaplanır.</div>",
                unsafe_allow_html=True,
            )
            st.write("")
            for i, adim in enumerate(st.session_state["adimlar"]):
                c1, c2 = st.columns([1, 1.4])
                with c1:
                    st.markdown(
                        f'<div style="padding-top:6px"><b>{adim["id"]}</b> '
                        f'<span class="altyazi">{adim["claim"]}</span></div>',
                        unsafe_allow_html=True,
                    )
                with c2:
                    yeni_kural = st.selectbox(
                        f"{adim['id']} gerekçesi",
                        KURAL_SECENEKLERI,
                        index=KURAL_SECENEKLERI.index(adim["rule"])
                        if adim["rule"] in KURAL_SECENEKLERI
                        else 0,
                        key=f"rule_{i}",
                        label_visibility="collapsed",
                    )
                    st.session_state["adimlar"][i]["rule"] = yeni_kural

            st.write("")
            with st.expander("Üretecin etiketi"):
                etiket = secilen["label"]
                st.markdown(
                    f"Sınıf `{etiket['error_class']}` · adım `{etiket['error_step']}` · "
                    f"çizim `{secilen['rendering']['bias']}`"
                )
                st.caption("Doğrulayıcıya verilmez; yalnızca karşılaştırma için.")


# --------------------------------------------------------------------------
# 2) Aynı problem, iki yanılgı
# --------------------------------------------------------------------------

with sekme2:
    ui.bolum("Neden nihai cevaba bakmak yetmez?")
    st.markdown(
        "Aşağıdaki iki çözüm **aynı problem ailesinden** ve ikisi de yanlış. Ama "
        "yanılgılar farklı, dolayısıyla öğretmenin müdahalesi de farklı olmalı. "
        "Sistem ikisini farklı teşhis eder ve **farklı adımı** işaretler."
    )

    ornekler = ornekleri_yukle()
    ciftler: dict[str, dict[str, dict]] = {}
    for s in ornekler:
        sinif = s["label"]["error_class"]
        if sinif in ("H1", "H3"):
            ciftler.setdefault(s["family"], {}).setdefault(sinif, s)
    uygun = [f for f, d in ciftler.items() if len(d) == 2]

    if not uygun:
        st.warning("Uygun çift bulunamadı.")
    else:
        aile2 = st.radio("Problem ailesi", uygun, horizontal=True, key="cift_aile")
        st.write("")
        kolonlar = st.columns(2, gap="large")
        for kol, sinif in zip(kolonlar, ("H1", "H3")):
            ornek = ciftler[aile2][sinif]
            with kol:
                b = vf.verify(ornek["figure"], ornek["steps"])
                ui.sonuc_karti(b.error_class, b.error_step, b.reason)
                st.markdown(f"**{ornek['soru']}**")
                st.write("")
                sekli_ciz(ornek, olcek=1.7)
                st.write("")
                for adim in ornek["steps"]:
                    ui.adim_satiri(adim, adim["id"] == b.error_step)

        st.info(
            "**Ayrım kuralı:** Öğrenci eksik koşulu ayrı bir adımda *verilen* diye "
            "iddia ettiyse **H1**, hiç anmadan teoremi uyguladıysa **H3**. "
            "Aynı eksik verilen, iki farklı yanılgı."
        )


# --------------------------------------------------------------------------
# 3) Çizim nasıl yanıltır?
# --------------------------------------------------------------------------

with sekme3:
    ui.bolum("Ders kitabı şekilleri ölçekli değildir")
    st.markdown(
        "Aşağıdaki iki çizimin **verilenleri birebir aynı** ve hiçbiri yalan "
        "söylemiyor — çünkü o bilgi zaten *verilmemiş*. Fark yalnızca verilmemiş "
        "niceliğin nasıl seçildiğinde."
    )

    ornekler = ornekleri_yukle()
    adaylar = [
        s
        for s in ornekler
        if s["label"]["error_class"] == "H1" and s["rendering"]["bias"] == "misleading"
    ]

    def tuzak_metni(solution: dict) -> tuple[str, str]:
        """Tuzağı örnekten okur; metin sabit yazılamaz.

        Bazı örneklerde tuzak diklik, bazılarında kenar eşliğidir. Yanlış metin
        doğru çizimin anlatısını bozar.
        """
        adim = next((a for a in solution["steps"] if a["rule"] == "verilen"), None)
        refs = (adim or {}).get("refs", {})
        if refs.get("asserts") == "perpendicular":
            return f"{refs.get('vertex', '?')} köşesinin dik olup olmadığını", "dik açı"
        if refs.get("asserts") == "congruent_segments":
            a, b = refs.get("segments", ["?", "?"])
            return f"|{a}| ile |{b}| kenarlarının eşit olup olmadığını", "eşit kenar"
        if refs.get("asserts") == "length":
            return (
                f"{refs.get('segment', '?')} uzunluğunun verilip verilmediğini",
                "verilen uzunluk",
            )
        return "şekilden ne okunabileceğini", "verilmemiş bir ilişki"

    if not adaylar:
        st.warning("Uygun örnek bulunamadı.")
    else:
        turler = sorted({tuzak_metni(s)[1] for s in adaylar})
        tur = st.radio("Tuzak türü", turler, horizontal=True, key="tuzak_tur")
        aday = next(s for s in adaylar if tuzak_metni(s)[1] == tur)
        soru_metni, tuzak_adi = tuzak_metni(aday)

        notr = copy.deepcopy(aday)
        notr["rendering"]["coords"] = renderer.layout(
            notr["figure"], "neutral", None, random.Random(7)
        )

        st.write("")
        st.markdown(f"**{aday['soru']}**")
        st.write("")

        k1, k2 = st.columns(2, gap="large")
        with k1:
            st.markdown("##### Yanıltıcı çizim")
            sekli_ciz(aday, olcek=2.1)
            st.error(f"İzleyicilerin çoğu burada **{tuzak_adi}** olduğunu söyler.")
        with k2:
            st.markdown("##### Nötr çizim")
            sekli_ciz(notr, olcek=2.1)
            st.success(f"Burada kimse {tuzak_adi} varsaymaz.")

        st.write("")
        alt1, alt2 = st.columns([1.2, 1])
        with alt1:
            st.info(
                f"**Sunum önerisi:** Soldaki şekli göster ve dinleyicilere "
                f"**{soru_metni}** sor. Çoğunluk *evet* der. Sonra verilenler "
                f"listesini aç — o bilgi yok."
            )
            b = vf.verify(aday["figure"], aday["steps"])
            ui.sonuc_karti(b.error_class, b.error_step, b.reason)
        with alt2:
            satirlar, eksikler = verilen_satirlari(aday["figure"])
            ui.verilenler_karti(satirlar, eksikler)
            st.write("")
            for adim in aday["steps"]:
                ui.adim_satiri(adim, adim["id"] == b.error_step)
