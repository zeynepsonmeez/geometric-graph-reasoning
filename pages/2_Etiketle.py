"""Elle yazılan küme için etiketleme arayüzü.

Protokol: docs/taksonomi.md §4.5

KÖRLÜK — bu sayfa bilinçli olarak GÖSTERMEZ:
  1. Diğer kodlayıcının etiketini. A2, A1'in kararını görürse κ ölçümü
     anlamsızlaşır; uyum, bağımsız kararların örtüşmesi olmalıdır.
  2. Sembolik doğrulayıcının teşhisini. Kodlayıcı doğrulayıcıyı görürse ona
     uyar; o zaman "doğrulayıcı insan etiketiyle ne kadar örtüşüyor?" sorusu
     kendi kendini doğrulayan bir döngüye dönüşür.

İkisi de kodda zorlanır, uyarıya bırakılmaz.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import handwritten as hw  # noqa: E402
import renderer  # noqa: E402
import visualize as viz  # noqa: E402

SINIFLAR = {
    "H0": "Hatasız — tüm adımlar geçerli",
    "H1": "Şekle aşırı güvenme — verilenlerde olmayan bilgiyi 'verilen' saymış",
    "H2": "Tanım karıştırma — yükseklik/kenarortay/açıortay veya kenar eşleştirme",
    "H3": "Ön koşulsuz teorem — koşulu hiç anmadan uygulamış",
}

st.set_page_config(page_title="Etiketle", layout="wide")
st.title("Elle yazılan küme — etiketleme")

cozumler = hw.load_solutions()
if not cozumler:
    st.warning(
        "Kümede henüz örnek yok. Önce **Örnek yaz** sayfasından örnek ekleyin."
    )
    st.stop()

ust = st.columns([1, 2])
with ust[0]:
    kodlayici = st.selectbox(
        "Kodlayıcı", ["A1", "A2"],
        help="A1 birincil, A2 ikincil. A2, A1'in etiketlerini görmez.",
    )

etiketler = hw.load_labels(kodlayici)

with ust[1]:
    kalan = [s for s in cozumler if s["problem_id"] not in etiketler]
    st.metric(
        "İlerleme", f"{len(etiketler)} / {len(cozumler)}",
        delta=f"{len(kalan)} kaldı" if kalan else "tamamlandı",
    )

st.caption(
    f"Bu sayfa diğer kodlayıcının etiketlerini ve doğrulayıcının teşhisini "
    f"göstermez. Kararı kendin ver."
)
st.divider()

sadece_kalan = st.checkbox("Yalnızca etiketlenmemişleri göster", value=bool(kalan))
havuz = kalan if (sadece_kalan and kalan) else cozumler

if not havuz:
    st.success("Bu kodlayıcı için etiketlenecek örnek kalmadı.")
    st.stop()

idx = st.number_input("Örnek", 0, len(havuz) - 1, 0)
secilen = havuz[int(idx)]
pid = secilen["problem_id"]

sol, sag = st.columns([1, 1])

with sol:
    st.subheader(f"{pid}")
    st.info(secilen.get("soru", "(soru metni yok)"))

    coords = secilen.get("rendering", {}).get("coords")
    if not coords:
        secilen = hw.fill_rendering(secilen)
        coords = secilen["rendering"]["coords"]

    st.image(
        renderer.to_svg(
            secilen["figure"], coords,
            secilen["rendering"].get("note", "Şekil ölçekli değildir."),
        ),
        use_container_width=False,
    )

    st.markdown("**Verilenler**")
    fig = secilen["figure"]
    satirlar = []
    for seg in fig.get("segments", []):
        tip = {"altitude": "yükseklik", "median": "kenarortay", "bisector": "açıortay"}.get(
            seg["type"]
        )
        if tip:
            satirlar.append(f"[{seg['from']}{seg['to']}] {tip}tir")
        if seg.get("length") is not None:
            satirlar.append(f"|{seg['from']}{seg['to']}| = {seg['length']}")
    for a in fig.get("angles", []):
        if a.get("value") is not None:
            satirlar.append(f"m({a['vertex']}) = {a['value']}°")
    for k in fig.get("perpendicular", []):
        satirlar.append(f"{k} köşesinde dik açı")
    for c in fig.get("congruent_segments", []):
        satirlar.append(f"|{c[0]}| = |{c[1]}|")
    for c in fig.get("similar", []):
        satirlar.append(f"{c[0]} ~ {c[1]}")
    st.markdown("\n".join(f"- {s}" for s in satirlar) or "- (verilen yok)")
    st.caption("Bu listede olmayan hiçbir ilişki verilmiş sayılmaz.")

with sag:
    st.subheader("Çözüm adımları")
    for adim in secilen["steps"]:
        with st.container(border=True):
            st.markdown(f"**{adim['id']}** &nbsp; {adim['claim']}")
            st.caption(f"gerekçe: {adim['rule']}")
            if adim.get("refs"):
                st.caption(f"referans: {adim['refs']}")

    st.image(viz.reasoning_graph_svg(secilen["steps"], None), use_container_width=False)

st.divider()
st.subheader("Kararın")

mevcut_etiket = etiketler.get(pid, {})
adim_secenekleri = ["(yok)"] + [a["id"] for a in secilen["steps"]]

k1, k2 = st.columns([2, 1])
with k1:
    sinif = st.radio(
        "Hata sınıfı",
        list(SINIFLAR),
        index=list(SINIFLAR).index(mevcut_etiket["error_class"])
        if mevcut_etiket.get("error_class") in SINIFLAR
        else 0,
        format_func=lambda s: f"{s} — {SINIFLAR[s]}",
    )
with k2:
    varsayilan = mevcut_etiket.get("error_step") or "(yok)"
    adim = st.selectbox(
        "Hatalı adım",
        adim_secenekleri,
        index=adim_secenekleri.index(varsayilan) if varsayilan in adim_secenekleri else 0,
        disabled=sinif == "H0",
        help="Topolojik sırada İLK geçersiz adım. H0 ise boş bırakılır.",
    )

with st.expander("Karar kuralları (docs/taksonomi.md §4.2–4.3)"):
    st.markdown(
        "**H1 mi H3 mü?** Öğrenci eksik koşulu ayrı bir adımda *verilen* diye "
        "iddia etmiş mi?\n"
        "- Evet → **H1**, hata o iddia adımındadır\n"
        "- Hayır, koşulu hiç anmadan teoremi uygulamış → **H3**\n\n"
        "**H2 mi H3 mü?**\n"
        "- Eleman tipi yanlış eşleştirilmiş (yükseklik↔kenarortay↔açıortay) → **H2**\n"
        "- Tip doğru ama başka bir ön koşul sağlanmıyor → **H3**\n\n"
        "**Tek hata kuralı:** ilk geçersiz adımı etiketle; ona bağlı sonraki "
        "adımlar kirlenmiştir, ayrıca hata sayılmaz.\n\n"
        "**Aritmetik hata** akıl yürütme hatası değildir; çıkarım doğruysa H0."
    )

if st.button("Etiketi kaydet", type="primary"):
    etiketler[pid] = {
        "error_class": sinif,
        "error_step": None if sinif == "H0" or adim == "(yok)" else adim,
    }
    hw.LABELS_DIR.mkdir(parents=True, exist_ok=True)
    (hw.LABELS_DIR / f"{kodlayici}.json").write_text(
        json.dumps(etiketler, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    st.success(f"`{pid}` → {sinif}" + (f" / {adim}" if sinif != "H0" else ""))
    st.rerun()

if etiketler:
    dagilim = Counter(v["error_class"] for v in etiketler.values())
    st.caption(
        f"{kodlayici} dağılımı: "
        + " · ".join(f"{k}: {dagilim.get(k, 0)}" for k in SINIFLAR)
    )
    st.caption(
        "Hedef dağılım bir kota değildir. Ne çıkarsa o raporlanır; "
        "dağılımı tutturmak için etiket değiştirilmez."
    )
