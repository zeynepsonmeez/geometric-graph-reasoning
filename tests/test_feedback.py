"""Öğrenciye yönelik geri bildirimin denetimi.

Geri bildirim, doğrulayıcının kararından TÜRETİLİR; kendi başına karar vermez.
Bu ayrım korunmalıdır: doğrulayıcı deneyde altın standarttır, geri bildirim
öğrenciye gider ve deneye hiç girmez.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import feedback as fb  # noqa: E402
import generator as gen  # noqa: E402
import verifier as vf  # noqa: E402

SOLUTIONS = gen.generate(total=300, seed=555)


def _ornek(sinif: str):
    sol = next(s for s in SOLUTIONS if s["label"]["error_class"] == sinif)
    bulgu = vf.verify_solution(sol)
    return sol, bulgu, fb.explain_finding(sol["figure"], sol["steps"], bulgu)


# --------------------------------------------------------------------------
# Bağımsızlık
# --------------------------------------------------------------------------


def test_geri_bildirim_kendi_karar_vermez() -> None:
    """explain() sinifi ve adimi disaridan alir; yeniden hesaplamaz."""
    sol = SOLUTIONS[0]
    uydurma = fb.explain(sol["figure"], sol["steps"], "H2", sol["steps"][0]["id"], "x")
    assert uydurma.baslik == "Kavramları birbirine karıştırdın"


def test_dogrulayiciyi_import_etmez() -> None:
    """feedback, verifier'i cagirmaz — yalnizca ciktisini bicimlendirir."""
    import ast

    kaynak = (ROOT / "src" / "feedback.py").read_text(encoding="utf-8")
    tree = ast.parse(kaynak)
    adlar = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            adlar.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            adlar.add(node.module.split(".")[0])
    assert "verifier" not in adlar and "generator" not in adlar


# --------------------------------------------------------------------------
# İçerik
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sinif", ["H1", "H2", "H3"])
def test_her_hata_sinifi_dort_bolumu_de_doldurur(sinif: str) -> None:
    _, _, f = _ornek(sinif)
    for alan in (f.baslik, f.ne_yaptin, f.neden_gecersiz, f.eksik_olan, f.oneri):
        assert alan and alan != "—", f"{sinif}: bos bolum"


def test_h1_eksik_verileni_adiyla_soyler() -> None:
    """'Eksik olan' hesaplanabilir bir alandir: neyin verilmesi gerektigini
    somut olarak yazar, 'yanlis' demekle yetinmez."""
    sol, bulgu, f = _ornek("H1")
    hatali = next(s for s in sol["steps"] if s["id"] == bulgu.error_step)
    refs = hatali.get("refs", {})

    if refs.get("asserts") == "perpendicular":
        assert refs["vertex"] in f.eksik_olan
        assert "90" in f.eksik_olan
    elif refs.get("asserts") == "congruent_segments":
        assert all(seg in f.eksik_olan for seg in refs["segments"])


def test_h1_sekil_uyarisini_icerir() -> None:
    _, _, f = _ornek("H1")
    assert "ölçekli değildir" in f.neden_gecersiz


def test_hatasiz_cozumde_gecersizlik_bolumu_yok() -> None:
    _, bulgu, f = _ornek("H0")
    assert bulgu.is_clean
    assert f.neden_gecersiz == "—" and f.eksik_olan == "—"
    md = f.as_markdown()
    assert "Neden geçersiz?" not in md, "bos bolum basiliyor"
    assert "Eksik olan" not in md


def test_adim_numarasi_okunur_sirayla_verilir() -> None:
    """Ogrenci 's3' demez, '3. adim' der."""
    for sinif in ("H1", "H2", "H3"):
        sol, bulgu, f = _ornek(sinif)
        sira = [s["id"] for s in sol["steps"]].index(bulgu.error_step) + 1
        assert f"{sira}. adımda" in f.ne_yaptin


def test_kirlenmis_adimlar_bildirilir() -> None:
    bulundu = False
    for sol in SOLUTIONS:
        bulgu = vf.verify_solution(sol)
        if bulgu.is_clean:
            continue
        f = fb.explain_finding(sol["figure"], sol["steps"], bulgu)
        bagli = [
            s["id"] for s in sol["steps"]
            if bulgu.error_step in (s.get("depends_on") or [])
        ]
        if bagli:
            assert f.kirlenmis, f"{sol['problem_id']}: kirlenmis adim bildirilmedi"
            bulundu = True
    assert bulundu, "bagimli adimi olan hic ornek yok"


# --------------------------------------------------------------------------
# Ders metinleri
# --------------------------------------------------------------------------


def test_benzerlik_hatasina_eleman_dersi_verilmez() -> None:
    """H2 iki bicimde ortaya cikar; karsilikli kenar eslestirme hatasina
    yukseklik/kenarortay dersi vermek yanlis yonlendirir."""
    for sol in SOLUTIONS:
        bulgu = vf.verify_solution(sol)
        if bulgu.error_class != "H2" or bulgu.violated != "correspondence":
            continue
        f = fb.explain_finding(sol["figure"], sol["steps"], bulgu)
        assert "köşe sırası" in f.oneri
        assert "Yükseklik dik iner" not in f.oneri
        return
    pytest.skip("eslestirme hatali H2 ornegi uretilmedi")


def test_eleman_karistirmasina_eslestirme_dersi_verilmez() -> None:
    for sol in SOLUTIONS:
        bulgu = vf.verify_solution(sol)
        if bulgu.error_class != "H2" or bulgu.violated != "segment_type":
            continue
        f = fb.explain_finding(sol["figure"], sol["steps"], bulgu)
        assert "Yükseklik dik iner" in f.oneri
        return
    pytest.skip("eleman tipi hatali H2 ornegi uretilmedi")


def test_h3_teorem_adi_tekrarlanmaz() -> None:
    """Dogrulayicinin mesaji '<teorem>: <gerekce>' bicimindedir; teorem adi
    zaten 'ne yaptin' satirinda gecer."""
    sol, bulgu, f = _ornek("H3")
    hatali = next(s for s in sol["steps"] if s["id"] == bulgu.error_step)
    import theorems

    t = theorems.get(hatali["rule"])
    if t:
        assert f.neden_gecersiz.count(t.name_tr) == 0


def test_tum_orneklerde_patlamaz() -> None:
    for sol in SOLUTIONS:
        bulgu = vf.verify_solution(sol)
        f = fb.explain_finding(sol["figure"], sol["steps"], bulgu)
        assert f.as_markdown().strip()


# --------------------------------------------------------------------------
# Yol gösterme: "nasıl ilerlemeliydin?"
# --------------------------------------------------------------------------


def _ornek_yol(sinif: str, violated: str | None = None):
    """Uygulanabilir kural listesi çağıran tarafça hesaplanır; feedback almaz."""
    for sol in SOLUTIONS:
        bulgu = vf.verify_solution(sol)
        if bulgu.error_class != sinif:
            continue
        if violated and bulgu.violated != violated:
            continue
        uygun = vf.applicable_rules(sol["figure"])
        return sol, bulgu, fb.explain_finding(sol["figure"], sol["steps"], bulgu, uygun)
    pytest.skip(f"{sinif}/{violated} ornegi bulunamadi")


@pytest.mark.parametrize("sinif", ["H1", "H2", "H3"])
def test_yol_gosterme_bos_degil(sinif: str) -> None:
    _, _, f = _ornek_yol(sinif)
    assert f.nasil.strip(), f"{sinif}: 'nasil ilerlemeliydin' bos"


def test_h1_yol_gostermesi_uygulanabilir_kurallari_sayar() -> None:
    sol, _, f = _ornek_yol("H1")
    from theorems import get

    for kid in vf.applicable_rules(sol["figure"]):
        t = get(kid)
        if t:
            assert t.name_tr in f.nasil, f"{kid} onerilmemis"


def test_h2_eleman_tipine_uyan_kurali_onerir() -> None:
    """Parca bir aciortaysa aciortay kurali onerilmelidir."""
    sol, bulgu, f = _ornek_yol("H2", "segment_type")
    hatali = next(s for s in sol["steps"] if s["id"] == bulgu.error_step)
    seg = hatali.get("refs", {}).get("segment")
    gercek = vf.segment_types(sol["figure"]).get(seg) or vf.segment_types(
        sol["figure"]
    ).get(seg[::-1] if seg else "")

    from theorems import get

    uyan = fb._tipe_uyan_kurallar(gercek)
    assert uyan, f"{gercek} tipine uyan kural yok"
    assert any(get(k).name_tr in f.nasil for k in uyan), f.nasil


def test_h2_eslestirme_hatasinda_benzerlik_ifadesi_hatirlatilir() -> None:
    sol, _, f = _ornek_yol("H2", "correspondence")
    benzer = sol["figure"]["similar"][0]
    assert benzer[0] in f.nasil and benzer[1] in f.nasil


def test_uygulanabilir_kurallar_gercekten_gecerli() -> None:
    """Onerilen her kuralin on kosulu gercekten saglanmali."""
    from theorems import get

    for sol in SOLUTIONS[:60]:
        for kid in vf.applicable_rules(sol["figure"]):
            t = get(kid)
            steps = [{"id": "s1", "claim": "", "rule": kid, "depends_on": [], "refs": {}}]
            bulgu = vf.verify(sol["figure"], steps)
            # dis_aci kullanım koşulu ister; availability listesinde olması normal
            if kid == "dis_aci":
                continue
            assert bulgu.is_clean, (
                f"{sol['problem_id']}: {kid} uygulanabilir sayildi ama "
                f"dogrulayici '{bulgu.error_class}' diyor"
            )


def test_uygulanamaz_kural_listede_yok() -> None:
    """Diklik verilmemisse pisagor onerilmemeli."""
    for sol in SOLUTIONS:
        if not sol["figure"].get("perpendicular"):
            assert "pisagor" not in vf.applicable_rules(sol["figure"])


def test_cozum_yoksa_durust_sekilde_soylenir() -> None:
    """Kalan kural yetmiyorsa bunu belirtmek durustluktur."""
    assert "soru eksik" in fb._yetmiyor_notu(["ic_acilar_toplami"])
    assert fb._yetmiyor_notu(["a", "b", "c"]) == ""


def test_yol_gosterme_markdown_da_gorunur() -> None:
    _, _, f = _ornek_yol("H3")
    assert "Nasıl ilerlemeliydin?" in f.as_markdown()
