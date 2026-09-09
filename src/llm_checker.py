"""Dil modeli denetleyici — projenin ölçülen tek bileşeni.

Araştırma sorusu: bir dil modeli, geometrik bir akıl yürütme zincirindeki hatayı,
sembolik bir doğrulayıcı kadar isabetli biçimde **yerelleştirebilir** mi?

Dört deney kolu (docs/taksonomi.md ve proje dokümanı Bölüm 9):

    K1  problem + çözüm adımları (düz metin)          — taban çizgi
    K2  K1 + şekil grafı (açık verilen listesi)       — ANA KOL
    K3  K2 + taksonomi tanımları + 3 örnek (few-shot) — üst sınır
    K4  K1 + çizilmiş şeklin görüntüsü                — isteğe bağlı

K1 ↔ K2 farkı, "graf temsili işe yarıyor mu?" sorusunun doğrudan ölçümüdür.

DİKKAT — mimari kuralları:
  1. Bu modül `verifier.py` ve `generator.py` modüllerini import ETMEZ.
     Model ne oracle'ı ne üreteci görür; deneyin geçerliliği buna dayanır.
  2. `label` alanı prompt'a ASLA girmez. `build_messages` yalnızca izin verilen
     alanları okur ve bir test bunu doğrular.
  Her ikisi de tests/test_independence.py ile denetlenir.

Yanıt biçimi yapılandırılmış çıktıyla (`output_config.format`) zorlanır; serbest
metin ayrıştırma riski yoktur.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "eval" / "results" / "cache"

ARMS = ("K1", "K2", "K3", "K4")
CLASSES = ("H0", "H1", "H2", "H3")

#: Deneyin varsayılan ayarları. Sonuç dosyalarına yazılır ki koşullar
#: bildiride birebir raporlanabilsin.
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"
DEFAULT_MAX_TOKENS = 2000

#: Modelden istenen yanıtın şeması. Alanlar Türkçedir; veri de Türkçedir.
YANIT_SEMASI: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hata_var_mi": {"type": "boolean"},
        "hata_sinifi": {"type": "string", "enum": list(CLASSES)},
        "hatali_adim": {"type": ["string", "null"]},
        "aciklama": {"type": "string"},
    },
    "required": ["hata_var_mi", "hata_sinifi", "hatali_adim", "aciklama"],
    "additionalProperties": False,
}


# --------------------------------------------------------------------------
# Prompt parçaları
# --------------------------------------------------------------------------

ROL = """Sen lise geometrisi konusunda uzman bir değerlendiricisin. Sana bir üçgen \
problemi ve bir öğrencinin çözüm adımları verilecek. Görevin, çözümde bir AKIL \
YÜRÜTME hatası olup olmadığını belirlemek; varsa hangi türden olduğunu ve HANGİ \
ADIMDA bulunduğunu söylemektir."""

#: Tüm kollara verilen asgari sınıf sözlüğü.
#:
#: Deney tasarımı kararı: sınıf adları tanımsız verilseydi görev tanımsız olurdu
#: ve M2 (sınıflama) hiçbir kol için anlamlı olmazdı. Bu yüzden HER kol tek
#: satırlık tanımları alır. K3'ün ayrıcalığı, tam tespit kuralları ve örneklerdir.
ASGARI_SINIFLAR = """Hata sınıfları:
- H0: Hata yok, çözüm geçerli.
- H1: Öğrenci şekilde GÖRÜNEN ama verilenlerde BULUNMAYAN bir bilgiyi doğru kabul etmiş.
- H2: Yükseklik / kenarortay / açıortay gibi kavramları birbiriyle karıştırmış ya da
  benzer üçgenlerde karşılıklı kenarları yanlış eşleştirmiş.
- H3: Bir teoremi, uygulanabilme koşulu sağlanmadan kullanmış."""

#: Yalnızca K3'e verilir.
TAM_TAKSONOMI = """Ayrıntılı tespit kuralları:

TEMEL İLKE — Verilenler listesinde yazmayan hiçbir ilişki "verilmiş" sayılmaz.
Şekil ölçekli değildir; çizimde öyle görünmesi bir bilgiyi verilen yapmaz.

H1 — Şekle aşırı güvenme
  Adımın dayandığı öznitelik verilenler arasında YOK ve öğrenci onu "verilen"
  gerekçesiyle kullanıyor. Hata, teoremin uygulandığı adımda değil, o bilgiyi
  "verilen" diye öne süren adımdadır.

H2 — Tanım karıştırma
  Kullanılan teoremin gerektirdiği eleman tipi ile şekildeki tip uyuşmuyor.
  Yükseklik dik iner; kenarortay kenarı ikiye böler; açıortay açıyı ikiye böler.
  Bu üçü yalnızca özel durumlarda çakışır. Benzerlikte köşe sırası karşılıklı
  kenarları belirler: ABC ~ DEF ise A↔D, B↔E, C↔F.

H3 — Teoremi ön koşulsuz uygulama
  Teorem doğru biliniyor ama koşulu sağlanmıyor ve öğrenci koşulu HİÇ ANMIYOR.
  Örnek: dik olduğu verilmemiş üçgende Pisagor; ikizkenar olduğu verilmemiş
  üçgende taban açıları eşitliği.

H1 ile H3 AYRIMI — tek soru:
  Öğrenci eksik koşulu ayrı bir adımda "verilen" diye iddia etmiş mi?
    Evet → H1 (hata o iddia adımındadır)
    Hayır, koşulu hiç anmadan teoremi uygulamış → H3

TEK HATA KURALI — Bir adım geçersizse ona bağlı sonraki adımlar da kirlenmiştir;
bunlar ayrıca hata sayılmaz. İLK geçersiz adımı bildir.

ARİTMETİK — Hesap hatası akıl yürütme hatası değildir. Çıkarım zinciri doğruysa
ve yalnızca aritmetik yanlışsa H0 bildir."""

#: K3'ün few-shot örnekleri. Değerlendirme kümelerinden ALINMAMIŞTIR; bu dosyada
#: elle yazılmıştır. Aksi hâlde model kendi test verisini görmüş olurdu.
FEW_SHOT = """Örnek 1
Problem: ABC üçgeninde |AB| = 5 br, |BC| = 7 br verilmiştir. |AC| kaç birimdir?
Verilenler: |AB| = 5, |BC| = 7. (Dik açı verilmemiş.)
Adımlar:
  s1: m(B) = 90    [gerekçe: verilen]
  s2: |AC|² = 5² + 7²    [gerekçe: pisagor]
Yanıt: {"hata_var_mi": true, "hata_sinifi": "H1", "hatali_adim": "s1",
"aciklama": "Dik açı verilenler arasında yok; şekilde öyle görünmesi onu verilen yapmaz."}

Örnek 2
Problem: KLM üçgeninde [KH] yüksekliktir, |LM| = 12 br'dir. |LH| kaç birimdir?
Verilenler: |LM| = 12, [KH] yükseklik.
Adımlar:
  s1: |LH| = |HM| = 6    [gerekçe: kenarortay]
Yanıt: {"hata_var_mi": true, "hata_sinifi": "H2", "hatali_adim": "s1",
"aciklama": "Kenarı ikiye bölme özelliği kenarortaya aittir; [KH] ise yüksekliktir."}

Örnek 3
Problem: DEF üçgeninde |DE| = 6 br, |DF| = 8 br, m(D) = 40° verilmiştir. m(E) kaç derecedir?
Verilenler: |DE| = 6, |DF| = 8, m(D) = 40.
Adımlar:
  s1: m(E) + m(F) = 140    [gerekçe: ic_acilar_toplami]
  s2: m(E) = m(F) = 70    [gerekçe: ikizkenar_taban]
Yanıt: {"hata_var_mi": true, "hata_sinifi": "H3", "hatali_adim": "s2",
"aciklama": "Taban açıları eşitliği ikizkenarlık gerektirir; 6 ≠ 8 ve eşlik verilmemiş."}"""

BICIM = """Yanıtını yalnızca şu alanlarla ver:
  hata_var_mi : true/false
  hata_sinifi : H0, H1, H2 veya H3
  hatali_adim : hatalı adımın kimliği (örn. "s2"); hata yoksa null
  aciklama    : tek cümlelik gerekçe"""


# --------------------------------------------------------------------------
# Prompt kurulumu
# --------------------------------------------------------------------------


def _figure_lines(figure: dict[str, Any]) -> list[str]:
    """Şekil grafını insan okunur verilen listesine çevirir (yalnızca K2/K3)."""
    satirlar: list[str] = []

    for seg in figure.get("segments") or []:
        ad = f"[{seg['from']}{seg['to']}]"
        tip = {
            "altitude": "yükseklik",
            "median": "kenarortay",
            "bisector": "açıortay",
        }.get(seg.get("type", "side"))
        if tip:
            satirlar.append(f"- {ad} {tip}tır")
        if seg.get("length") is not None:
            satirlar.append(f"- |{seg['from']}{seg['to']}| = {seg['length']}")

    for aci in figure.get("angles") or []:
        if aci.get("value") is not None:
            satirlar.append(f"- m({aci['vertex']}) = {aci['value']}°")

    for kose in figure.get("perpendicular") or []:
        satirlar.append(f"- {kose} köşesinde dik açı vardır")

    for cift in figure.get("congruent_segments") or []:
        satirlar.append(f"- |{cift[0]}| = |{cift[1]}|")

    for cift in figure.get("similar") or []:
        satirlar.append(f"- {cift[0]} ~ {cift[1]} (köşe sırası karşılıklıdır)")

    return satirlar


def _step_lines(steps: list[dict[str, Any]]) -> list[str]:
    return [
        f"  {st['id']}: {st['claim']}    [gerekçe: {st['rule']}]" for st in steps
    ]


def build_messages(solution: dict[str, Any], arm: str) -> tuple[str, str]:
    """(sistem, kullanıcı) metinlerini kurar.

    `solution["label"]` alanına ERİŞİLMEZ. Prompt yalnızca soru, şekil ve
    adımlardan oluşur; bir test iki farklı etikete sahip aynı çözümün özdeş
    prompt ürettiğini doğrular.
    """
    if arm not in ARMS:
        raise ValueError(f"bilinmeyen kol: {arm}")

    sistem = [ROL, "", ASGARI_SINIFLAR]
    if arm == "K3":
        sistem += ["", TAM_TAKSONOMI, "", FEW_SHOT]
    sistem += ["", BICIM]

    kullanici = [f"Problem: {solution.get('soru', '')}", ""]

    if arm in ("K2", "K3"):
        satirlar = _figure_lines(solution["figure"])
        kullanici.append("Verilenler:")
        kullanici += satirlar or ["- (verilen yok)"]
        kullanici.append(
            "Bu listede yazmayan hiçbir ilişki verilmiş sayılmaz."
        )
        kullanici.append("")

    kullanici.append("Öğrencinin çözüm adımları:")
    kullanici += _step_lines(solution["steps"])

    return "\n".join(sistem), "\n".join(kullanici)


def prompt_fingerprint(system: str, user: str) -> str:
    """Prompt değişirse önbellek geçersizleşsin diye kısa özet."""
    return hashlib.sha256((system + "\x00" + user).encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# Yanıt
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Prediction:
    hata_var_mi: bool | None = None
    hata_sinifi: str | None = None
    hatali_adim: str | None = None
    aciklama: str = ""
    error: str | None = None
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and self.hata_sinifi in CLASSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "hata_var_mi": self.hata_var_mi,
            "hata_sinifi": self.hata_sinifi,
            "hatali_adim": self.hatali_adim,
            "aciklama": self.aciklama,
            "error": self.error,
            "usage": self.usage,
        }


def parse_response(text: str, usage: dict[str, int] | None = None) -> Prediction:
    """Yapılandırılmış yanıtı okur.

    `output_config.format` geçerli JSON garantiler; yine de bozuk yanıt sessizce
    geçmesin diye açıkça yakalanır — başarısız çağrı, yanlış tahminden farklı
    raporlanmalıdır.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return Prediction(error=f"JSON cozulemedi: {e}", usage=usage or {})

    sinif = data.get("hata_sinifi")
    if sinif not in CLASSES:
        return Prediction(error=f"gecersiz sinif: {sinif!r}", usage=usage or {})

    adim = data.get("hatali_adim")
    if sinif == "H0":
        adim = None

    return Prediction(
        hata_var_mi=data.get("hata_var_mi"),
        hata_sinifi=sinif,
        hatali_adim=adim,
        aciklama=data.get("aciklama", ""),
        usage=usage or {},
    )


# --------------------------------------------------------------------------
# İstemci
# --------------------------------------------------------------------------


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> tuple[str, dict[str, int]]: ...


class FakeClient:
    """Çevrimdışı test istemcisi. Ağ çağrısı yapmaz, ücret doğurmaz."""

    def __init__(self, yanit: dict[str, Any] | None = None) -> None:
        self.yanit = yanit or {
            "hata_var_mi": True,
            "hata_sinifi": "H1",
            "hatali_adim": "s1",
            "aciklama": "sahte yanit",
        }
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> tuple[str, dict[str, int]]:
        self.calls.append((system, user))
        return json.dumps(self.yanit, ensure_ascii=False), {
            "input_tokens": 0,
            "output_tokens": 0,
        }


class AnthropicClient:
    """Claude API istemcisi.

    - Yanıt biçimi `output_config.format` ile zorlanır.
    - Sistem metni önbelleğe alınır; 430 örnek boyunca aynı kaldığı için
      girdi maliyetinin büyük bölümünü düşürür.
    - Örnekleme parametresi (`temperature` vb.) GÖNDERİLMEZ: güncel modellerde
      kaldırılmıştır ve gönderilirse istek reddedilir.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = DEFAULT_EFFORT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        import anthropic  # yerel import: paket yoksa modül yine de yüklenir

        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic()

    def complete(self, system: str, user: str) -> tuple[str, dict[str, int]]:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": YANIT_SEMASI},
            },
        )

        if response.stop_reason == "refusal":
            raise RuntimeError("model istegi reddetti (stop_reason=refusal)")

        text = next((b.text for b in response.content if b.type == "text"), "")
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_input_tokens": getattr(
                response.usage, "cache_read_input_tokens", 0
            ),
        }
        return text, usage


def default_client(**kwargs: Any) -> LLMClient:
    """Anahtar varsa gerçek istemci, yoksa açık hata."""
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError(
            "API anahtari bulunamadi. .env dosyasina ANTHROPIC_API_KEY koyun "
            "(.gitignore'dadir) veya cevrimdisi denemeler icin FakeClient kullanin."
        )
    return AnthropicClient(**kwargs)


# --------------------------------------------------------------------------
# Çalıştırma ve önbellek
# --------------------------------------------------------------------------


def _cache_path(arm: str, model: str, problem_id: str, repeat: int, fp: str) -> Path:
    return CACHE_DIR / arm / model / f"{problem_id}_r{repeat}_{fp}.json"


def ask(
    solution: dict[str, Any],
    arm: str,
    client: LLMClient,
    repeat: int = 0,
    model: str = DEFAULT_MODEL,
    use_cache: bool = True,
) -> Prediction:
    """Tek bir örnek için modeli sorgular.

    Sonuçlar diske önbelleklenir: deney yeniden çalıştırıldığında aynı çağrı
    tekrar ücretlendirilmez. Prompt değişirse parmak izi değişir ve önbellek
    kendiliğinden geçersizleşir.
    """
    system, user = build_messages(solution, arm)
    fp = prompt_fingerprint(system, user)
    path = _cache_path(arm, model, solution["problem_id"], repeat, fp)

    if use_cache and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return Prediction(**data)

    try:
        text, usage = client.complete(system, user)
        pred = parse_response(text, usage)
    except Exception as e:  # ağ/API hatası tahmin hatasından ayrı raporlanır
        pred = Prediction(error=f"{type(e).__name__}: {e}")

    if use_cache and pred.error is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(pred.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return pred


# --------------------------------------------------------------------------
# Maliyet kestirimi
# --------------------------------------------------------------------------

#: USD / 1M token. Kaynak: proje dokümanı; fiyat değişirse burası güncellenir.
FIYAT = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def estimate_cost(
    n_solutions: int,
    arms: tuple[str, ...] = ("K1", "K2", "K3"),
    repeats: int = 2,
    model: str = DEFAULT_MODEL,
    avg_input: int = 700,
    avg_output: int = 200,
) -> dict[str, float]:
    """Kaba maliyet kestirimi. Deneyi başlatmadan önce görülmelidir."""
    calls = n_solutions * len(arms) * repeats
    girdi, cikti = FIYAT.get(model, FIYAT[DEFAULT_MODEL])
    return {
        "cagri": calls,
        "girdi_usd": calls * avg_input / 1_000_000 * girdi,
        "cikti_usd": calls * avg_output / 1_000_000 * cikti,
        "toplam_usd": calls * (avg_input / 1_000_000 * girdi + avg_output / 1_000_000 * cikti),
    }
