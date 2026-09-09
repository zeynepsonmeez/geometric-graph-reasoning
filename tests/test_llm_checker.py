"""Dil modeli kolunun denetimi.

Tüm testler **çevrimdışıdır**: `FakeClient` kullanılır, ağ çağrısı yapılmaz,
ücret doğmaz. Denetlenen şey prompt kurulumu, sızıntı yokluğu ve yanıt işleme.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import generator as gen  # noqa: E402
import llm_checker as llm  # noqa: E402

SOLUTIONS = gen.generate(total=40, seed=555)
ORNEK = SOLUTIONS[0]


# --------------------------------------------------------------------------
# Sızıntı — deneyin geçerliliği buna bağlı
# --------------------------------------------------------------------------


@pytest.mark.parametrize("arm", llm.ARMS)
def test_prompt_etiketi_sizdirmaz(arm: str) -> None:
    """Aynı çözüm, farklı etiketlerle özdeş prompt üretmelidir."""
    a = copy.deepcopy(ORNEK)
    b = copy.deepcopy(ORNEK)
    a["label"] = {"error_class": "H0", "error_step": None, "source": "x"}
    b["label"] = {"error_class": "H3", "error_step": "s1", "source": "y"}

    assert llm.build_messages(a, arm) == llm.build_messages(b, arm)


@pytest.mark.parametrize("arm", llm.ARMS)
def test_prompt_cozum_uretecini_ele_vermez(arm: str) -> None:
    """Prompt'ta sablon kimligi, varyant adi veya uretec izi bulunmamali.

    Not: 'hatali_adim' bilincli olarak listede degildir — modelden istenen
    ciktinin alan adidir, sizinti degil.
    """
    system, user = llm.build_messages(ORNEK, arm)
    metin = system + user
    for sizinti in ("template_id", "varyant", "figure_override", "generator", "T01"):
        assert sizinti not in metin, f"{arm}: prompt'ta '{sizinti}' gecmemeli"


def test_prompt_koordinat_icermez() -> None:
    """Cizim koordinatlari metin kollarina girmez (K4 goruntuyle calisir)."""
    for arm in ("K1", "K2", "K3"):
        system, user = llm.build_messages(ORNEK, arm)
        assert "coords" not in system + user


# --------------------------------------------------------------------------
# Kol farkları — K1 ↔ K2 projenin ana ölçümü
# --------------------------------------------------------------------------


def test_k1_verilenleri_gostermez() -> None:
    _, user = llm.build_messages(ORNEK, "K1")
    assert "Verilenler:" not in user


def test_k2_verilenleri_gosterir() -> None:
    _, user = llm.build_messages(ORNEK, "K2")
    assert "Verilenler:" in user
    assert "yazmayan hiçbir ilişki verilmiş sayılmaz" in user


def test_k1_ve_k2_yalnizca_verilenlerde_ayrisir() -> None:
    """Iki kol arasindaki TEK fark sekil grafi olmali; aksi halde K1<->K2
    farki graf temsilinin katkisini olcmez."""
    s1, u1 = llm.build_messages(ORNEK, "K1")
    s2, u2 = llm.build_messages(ORNEK, "K2")

    assert s1 == s2, "sistem metni kollar arasinda degismemeli"
    assert "Öğrencinin çözüm adımları:" in u1 and "Öğrencinin çözüm adımları:" in u2
    assert u1.split("Öğrencinin çözüm adımları:")[1] == u2.split("Öğrencinin çözüm adımları:")[1]


def test_k3_taksonomi_ve_ornek_ekler() -> None:
    s2, _ = llm.build_messages(ORNEK, "K2")
    s3, _ = llm.build_messages(ORNEK, "K3")

    assert len(s3) > len(s2)
    assert "Ayrıntılı tespit kuralları" in s3
    assert "Örnek 1" in s3
    assert "Ayrıntılı tespit kuralları" not in s2


def test_tum_kollar_asgari_sinif_tanimini_alir() -> None:
    """Sinif adlari tanimsiz verilseydi gorev tanimsiz olurdu ve M2 hicbir
    kol icin anlamli olmazdi."""
    for arm in llm.ARMS:
        system, _ = llm.build_messages(ORNEK, arm)
        for sinif in llm.CLASSES:
            assert f"{sinif}:" in system, f"{arm}: {sinif} tanimi yok"


def test_few_shot_ornekleri_degerlendirme_kumesinden_degil() -> None:
    """K3'un ornekleri elle yazilmistir; test verisinden alinmis olamaz."""
    sorular = {s["soru"] for s in gen.generate(total=400, seed=20260906)}
    for satir in llm.FEW_SHOT.splitlines():
        if satir.startswith("Problem: "):
            assert satir[len("Problem: "):] not in sorular


def test_bilinmeyen_kol_reddedilir() -> None:
    with pytest.raises(ValueError):
        llm.build_messages(ORNEK, "K9")


# --------------------------------------------------------------------------
# Yanıt işleme
# --------------------------------------------------------------------------


def test_gecerli_yanit_okunur() -> None:
    p = llm.parse_response(json.dumps({
        "hata_var_mi": True, "hata_sinifi": "H2",
        "hatali_adim": "s3", "aciklama": "gerekce",
    }))
    assert p.ok and p.hata_sinifi == "H2" and p.hatali_adim == "s3"


def test_h0_yanitinda_adim_bosaltilir() -> None:
    """Model H0 derken adim bildirirse tutarsizlik olur; adim null'a cekilir."""
    p = llm.parse_response(json.dumps({
        "hata_var_mi": False, "hata_sinifi": "H0",
        "hatali_adim": "s2", "aciklama": "",
    }))
    assert p.hatali_adim is None


def test_bozuk_json_hata_olarak_isaretlenir() -> None:
    p = llm.parse_response("bu json degil")
    assert not p.ok and p.error and "JSON" in p.error


def test_gecersiz_sinif_hata_olarak_isaretlenir() -> None:
    p = llm.parse_response(json.dumps({
        "hata_var_mi": True, "hata_sinifi": "H9",
        "hatali_adim": "s1", "aciklama": "",
    }))
    assert not p.ok and "gecersiz sinif" in (p.error or "")


def test_semada_dort_alan_zorunlu() -> None:
    assert set(llm.YANIT_SEMASI["required"]) == {
        "hata_var_mi", "hata_sinifi", "hatali_adim", "aciklama"
    }
    assert llm.YANIT_SEMASI["additionalProperties"] is False
    assert llm.YANIT_SEMASI["properties"]["hata_sinifi"]["enum"] == list(llm.CLASSES)


# --------------------------------------------------------------------------
# Çalıştırma ve önbellek
# --------------------------------------------------------------------------


def test_ask_sahte_istemciyle_calisir() -> None:
    client = llm.FakeClient()
    p = llm.ask(ORNEK, "K2", client, use_cache=False)
    assert p.ok and len(client.calls) == 1


def test_api_hatasi_tahminden_ayri_raporlanir() -> None:
    """Basarisiz cagri, yanlis tahminle ayni kefeye konmamali."""

    class Patlayan:
        def complete(self, system: str, user: str):
            raise ConnectionError("ag yok")

    p = llm.ask(ORNEK, "K1", Patlayan(), use_cache=False)
    assert not p.ok
    assert p.error and "ConnectionError" in p.error
    assert p.hata_sinifi is None


def test_prompt_degisince_parmak_izi_degisir() -> None:
    a = llm.prompt_fingerprint(*llm.build_messages(ORNEK, "K1"))
    b = llm.prompt_fingerprint(*llm.build_messages(ORNEK, "K2"))
    assert a != b


def test_onbellek_ikinci_cagriyi_engeller(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    client = llm.FakeClient()

    ilk = llm.ask(ORNEK, "K2", client)
    ikinci = llm.ask(ORNEK, "K2", client)

    assert len(client.calls) == 1, "ikinci cagri onbellekten gelmeliydi"
    assert ilk.hata_sinifi == ikinci.hata_sinifi


def test_hatali_yanit_onbelleklenmez(tmp_path, monkeypatch) -> None:
    """Basarisiz cagri diske yazilirsa hata kalicilasir."""
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)

    class Patlayan:
        def complete(self, system: str, user: str):
            raise ConnectionError("ag yok")

    llm.ask(ORNEK, "K1", Patlayan())
    assert not list(tmp_path.rglob("*.json"))


# --------------------------------------------------------------------------
# Maliyet
# --------------------------------------------------------------------------


def test_maliyet_kestirimi_makul() -> None:
    ozet = llm.estimate_cost(n_solutions=430, arms=("K1", "K2", "K3"), repeats=2)
    assert ozet["cagri"] == 430 * 3 * 2
    assert 0 < ozet["toplam_usd"] < 500


def test_ucuz_model_daha_ucuz() -> None:
    opus = llm.estimate_cost(100, model="claude-opus-5")["toplam_usd"]
    haiku = llm.estimate_cost(100, model="claude-haiku-4-5")["toplam_usd"]
    assert haiku < opus
