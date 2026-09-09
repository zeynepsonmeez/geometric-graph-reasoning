"""Arayüzün paylaşılan görsel dili.

Üç sayfa da buradan beslenir; böylece tipografi, boşluk ve renk kararları tek
yerde durur ve sayfalar birbirinden ayrışmaz.

Tasarım kararları:
  - Aydınlık zemin: geometrik çizimler beyaz üzerinde koyu temaya göre çok daha
    net okunur, yazdırılmış ekran görüntüsü de düzgün çıkar.
  - Başlıklarda serif, gövdede sans: akademik belge hissi.
  - Streamlit'in kendi çerçevesi (Deploy butonu, menü) gizlenir; sunumda
    prototip görüntüsü verir.
  - Sonuç kartı sayfanın en baskın öğesidir — projenin çıktısı odur.
"""

from __future__ import annotations

import streamlit as st

NAVY = "#22345e"
TEAL = "#0e6f66"
RED = "#a3251f"
AMBER = "#9a6100"
VIOLET = "#5a3a86"
MUTED = "#5b6472"
LINE = "#dfe3ea"
SOFT = "#f6f8fb"

SINIF_RENK = {"H0": TEAL, "H1": RED, "H2": VIOLET, "H3": AMBER}
SINIF_ZEMIN = {"H0": "#e6f2f0", "H1": "#fdecea", "H2": "#f3edfa", "H3": "#fff8e8"}

SINIF_ADI = {
    "H0": "Hatasız",
    "H1": "Şekle Aşırı Güvenme",
    "H2": "Tanım Karıştırma",
    "H3": "Teoremi Ön Koşulsuz Uygulama",
}

_CSS = f"""
<style>
/* Streamlit cercevesini gizle — sunumda prototip goruntusu veriyor */
#MainMenu, header[data-testid="stHeader"], footer {{ visibility: hidden; height: 0; }}
.stDeployButton, [data-testid="stToolbar"] {{ display: none !important; }}

.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1220px; }}

h1, h2, h3 {{ font-family: Georgia, "Times New Roman", serif !important; color: {NAVY}; }}
h1 {{ font-size: 2.1rem !important; letter-spacing: -0.4px; margin-bottom: .2rem !important; }}
h2 {{ font-size: 1.35rem !important; margin-top: 1.4rem !important; }}
h3 {{ font-size: 1.1rem !important; }}

/* Sekmeler */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{
  font-weight: 600; font-size: .94rem; padding: 10px 18px;
  border-radius: 6px 6px 0 0; color: {MUTED};
}}
.stTabs [aria-selected="true"] {{ color: {NAVY} !important; background: {SOFT}; }}

/* Kenar cubugu */
[data-testid="stSidebar"] {{ background: {SOFT}; border-right: 1px solid {LINE}; }}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.5rem; }}

/* Sekil kutusu — cizim beyaz zeminde, cerceveli */
.sekil-kutu {{
  background: #fff; border: 1px solid {LINE}; border-radius: 10px;
  padding: 14px; text-align: center;
  box-shadow: 0 1px 3px rgba(26,28,34,.05);
}}
.sekil-kutu svg {{ max-width: 100%; height: auto; }}

/* Sonuc karti — sayfanin en baskin ogesi */
.sonuc {{
  border-radius: 12px; padding: 20px 24px; margin: 4px 0 14px;
  border-left: 7px solid; box-shadow: 0 2px 8px rgba(26,28,34,.07);
}}
.sonuc .sinif {{
  font-family: Georgia, serif; font-size: 1.5rem; font-weight: 700;
  line-height: 1.25; margin-bottom: 2px;
}}
.sonuc .kod {{
  font-size: .78rem; font-weight: 700; letter-spacing: 1.2px;
  text-transform: uppercase; opacity: .75;
}}
.sonuc .adim {{
  display: inline-block; margin: 10px 0 8px; padding: 5px 14px;
  border-radius: 20px; font-weight: 700; font-size: .92rem;
  background: rgba(255,255,255,.75); border: 1px solid rgba(0,0,0,.09);
}}
.sonuc .gerekce {{ font-size: .95rem; line-height: 1.6; color: {NAVY}; opacity: .92; }}

/* Verilenler listesi */
.veri {{
  background: {SOFT}; border: 1px solid {LINE}; border-radius: 10px;
  padding: 14px 18px; font-size: .92rem; line-height: 1.85;
}}
.veri b {{ color: {NAVY}; }}
.veri .yok {{ color: {RED}; font-weight: 600; }}

/* Adim satiri */
.adim-satir {{
  border: 1px solid {LINE}; border-left: 4px solid {LINE};
  border-radius: 8px; padding: 9px 14px; margin-bottom: 7px; background: #fff;
}}
.adim-satir.hatali {{ border-left-color: {RED}; background: {SINIF_ZEMIN["H1"]}; }}
.adim-satir .kimlik {{ font-weight: 700; color: {NAVY}; margin-right: 8px; }}
.adim-satir .kural {{ font-size: .8rem; color: {MUTED}; }}

/* Bolum basligi */
.bolum {{
  font-family: Georgia, serif; font-size: 1.15rem; font-weight: 700;
  color: {NAVY}; border-bottom: 2px solid {NAVY};
  padding-bottom: 5px; margin: 18px 0 12px;
}}

.altyazi {{ color: {MUTED}; font-size: .88rem; line-height: 1.6; }}
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def baslik(metin: str, altyazi: str = "") -> None:
    st.markdown(f"# {metin}")
    if altyazi:
        st.markdown(f'<div class="altyazi">{altyazi}</div>', unsafe_allow_html=True)
    st.write("")


def bolum(metin: str) -> None:
    st.markdown(f'<div class="bolum">{metin}</div>', unsafe_allow_html=True)


def sekil(svg: str) -> None:
    st.markdown(f'<div class="sekil-kutu">{svg}</div>', unsafe_allow_html=True)


def sonuc_karti(sinif: str, adim: str | None, gerekce: str) -> None:
    """Hata teşhisi — sayfanın en baskın öğesi.

    Projenin çıktısı "yanlış" değil, konumu belli bir teşhistir; kart bunu
    görsel olarak da öne çıkarır.
    """
    renk = SINIF_RENK.get(sinif, NAVY)
    zemin = SINIF_ZEMIN.get(sinif, SOFT)
    isaret = "✓" if sinif == "H0" else "✗"

    adim_rozet = (
        f'<div class="adim" style="color:{renk}">Hatalı adım: {adim}</div>'
        if adim
        else ""
    )

    st.markdown(
        f"""<div class="sonuc" style="background:{zemin};border-left-color:{renk}">
  <div class="kod" style="color:{renk}">{sinif}</div>
  <div class="sinif" style="color:{renk}">{isaret} {SINIF_ADI.get(sinif, sinif)}</div>
  {adim_rozet}
  <div class="gerekce">{gerekce}</div>
</div>""",
        unsafe_allow_html=True,
    )


def verilenler_karti(satirlar: list[str], eksikler: list[str] | None = None) -> None:
    govde = "".join(f"• {s}<br>" for s in satirlar) or "• (verilen yok)<br>"
    eksik_html = ""
    if eksikler:
        eksik_html = (
            f'<div class="yok" style="margin-top:8px">Verilmeyen: '
            f'{", ".join(eksikler)}</div>'
            '<div style="font-size:.82rem;color:#5b6472;margin-top:2px">'
            "Çizimde öyle görünmesi onu verilen yapmaz.</div>"
        )
    st.markdown(
        f'<div class="veri"><b>Verilenler</b><br>{govde}{eksik_html}</div>',
        unsafe_allow_html=True,
    )


def adim_satiri(adim: dict, hatali: bool = False) -> None:
    sinif = " hatali" if hatali else ""
    st.markdown(
        f'<div class="adim-satir{sinif}">'
        f'<span class="kimlik">{adim["id"]}</span>{adim.get("claim", "")}'
        f'<div class="kural">gerekçe: {adim.get("rule", "")}</div></div>',
        unsafe_allow_html=True,
    )
