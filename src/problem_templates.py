"""Problem şablonlarının yüklenmesi ve denetimi.

Şablonlar `data/problems/*.json` altında durur. Her şablon bir problem ailesinden
(P1–P6) örnek üretmek için gereken her şeyi içerir:

- `parametreler` : rastgeleleştirilecek yer tutucular ({V0}, {a}, ...)
- `kisitlar`     : geometrik tutarlılığı koruyan koşullar
- `figure_base`  : tüm varyantların ortak şekil tanımı
- `varyantlar`   : H0 (doğru çözüm) ve enjekte edilebilir hata varyantları

Tasarım kararı: hata varyantları şablonda **açıkça yazılır**, üreteç hata kurgusunu
kendisi uydurmaz. Böylece her örneğin neden o sınıfa girdiği insan tarafından
denetlenebilir kalır (`varyant.not` alanı).

Bu modül `theorems.py`'yi import ETMEZ — üreteç tarafında yer alır ve doğrulayıcıdan
bağımsızdır. Bkz. tests/test_independence.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROBLEMS_DIR = Path(__file__).resolve().parent.parent / "data" / "problems"

#: Metinlerdeki {ad} biçimindeki yer tutucular.
PLACEHOLDER = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")

VALID_CLASSES = {"H0", "H1", "H2", "H3"}


@dataclass(frozen=True)
class Variant:
    sinif: str
    hatali_adim: str | None
    bias: str
    soru: str
    steps: list[dict[str, Any]]
    figure_override: dict[str, Any]
    aciklama: str = ""

    @property
    def step_ids(self) -> set[str]:
        return {s["id"] for s in self.steps}


@dataclass(frozen=True)
class Template:
    template_id: str
    family: str
    baslik: str
    kazanim_kodu: str | None
    parametreler: dict[str, dict[str, Any]]
    kisitlar: list[str]
    figure_base: dict[str, Any]
    varyantlar: list[Variant]

    @property
    def classes(self) -> set[str]:
        return {v.sinif for v in self.varyantlar}

    def placeholder_names(self) -> set[str]:
        """Şablonun parametrelerinden türeyen tüm geçerli yer tutucu adları."""
        names: set[str] = set()
        for ad, tanim in self.parametreler.items():
            tip = tanim["tip"]
            if tip == "vertex_triple":
                names.update(f"{ad}{i}" for i in range(3))
            elif tip == "vertex_sextuple":
                names.update(f"{ad}{i}" for i in range(6))
            else:
                names.add(ad)
        return names


def _to_variant(raw: dict[str, Any]) -> Variant:
    return Variant(
        sinif=raw["sinif"],
        hatali_adim=raw["hatali_adim"],
        bias=raw["bias"],
        soru=raw["soru"],
        steps=raw["steps"],
        figure_override=raw.get("figure_override", {}),
        aciklama=raw.get("not", ""),
    )


def load(path: Path) -> Template:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Template(
        template_id=raw["template_id"],
        family=raw["family"],
        baslik=raw["baslik"],
        kazanim_kodu=raw.get("kazanim_kodu"),
        parametreler=raw["parametreler"],
        kisitlar=raw.get("kisitlar", []),
        figure_base=raw["figure_base"],
        varyantlar=[_to_variant(v) for v in raw["varyantlar"]],
    )


def load_all(directory: Path | None = None) -> list[Template]:
    """Tüm şablonları template_id sırasına göre yükler."""
    directory = directory or PROBLEMS_DIR
    paths = sorted(directory.glob("P?-T??.json"))
    return [load(p) for p in paths]


def collect_placeholders(node: Any) -> set[str]:
    """İç içe bir yapıdaki tüm {yer_tutucu} adlarını toplar."""
    found: set[str] = set()
    if isinstance(node, str):
        found.update(PLACEHOLDER.findall(node))
    elif isinstance(node, dict):
        for value in node.values():
            found |= collect_placeholders(value)
    elif isinstance(node, list):
        for item in node:
            found |= collect_placeholders(item)
    return found


def check(template: Template) -> list[str]:
    """Şablonun iç tutarlılığını denetler; sorun listesi döndürür (boşsa temiz).

    Şema doğrulamasının yakalayamadığı anlamsal kuralları denetler.
    """
    problems: list[str] = []
    tid = template.template_id

    if not tid.startswith(template.family + "-"):
        problems.append(f"{tid}: template_id ile family uyuşmuyor")

    if "H0" not in template.classes:
        problems.append(f"{tid}: H0 (doğru çözüm) varyantı yok")

    if template.classes == {"H0"}:
        problems.append(f"{tid}: hiç hata varyantı yok")

    bilinen = template.placeholder_names()
    kullanilan = collect_placeholders(
        {"f": template.figure_base, "v": [(v.soru, v.steps, v.figure_override) for v in template.varyantlar]}
    )
    for eksik in sorted(kullanilan - bilinen):
        problems.append(f"{tid}: '{{{eksik}}}' kullanılıyor ama parametrelerde tanımlı değil")

    for v in template.varyantlar:
        etiket = f"{tid}/{v.sinif}"

        if v.sinif not in VALID_CLASSES:
            problems.append(f"{etiket}: bilinmeyen sınıf")

        if v.sinif == "H0":
            if v.hatali_adim is not None:
                problems.append(f"{etiket}: H0 varyantında hatali_adim null olmalı")
        else:
            if v.hatali_adim is None:
                problems.append(f"{etiket}: hata varyantında hatali_adim null olamaz")
            elif v.hatali_adim not in v.step_ids:
                problems.append(f"{etiket}: hatali_adim '{v.hatali_adim}' adımlar arasında yok")
            if not v.aciklama:
                problems.append(f"{etiket}: 'not' alanı boş — sınıf gerekçesi yazılmalı")

        # depends_on yalnızca kendinden ÖNCEKİ adımlara işaret edebilir (DAG, çevrimsiz)
        gorulen: set[str] = set()
        for step in v.steps:
            for dep in step["depends_on"]:
                if dep not in gorulen:
                    problems.append(
                        f"{etiket}/{step['id']}: '{dep}' adımına bağlı ama o adım daha sonra geliyor"
                    )
            gorulen.add(step["id"])

    return problems


def check_all(templates: list[Template]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for t in templates:
        if t.template_id in seen:
            problems.append(f"{t.template_id}: yinelenen template_id")
        seen.add(t.template_id)
        problems.extend(check(t))
    return problems


if __name__ == "__main__":
    templates = load_all()
    print(f"{len(templates)} sablon yuklendi\n")

    for t in templates:
        siniflar = ", ".join(sorted(t.classes))
        kazanim = t.kazanim_kodu or "TODO"
        print(f"  {t.template_id}  {t.family}  [{siniflar}]  kazanim={kazanim}")
        print(f"      {t.baslik}")

    sorunlar = check_all(templates)
    print()
    if sorunlar:
        print(f"{len(sorunlar)} sorun bulundu:")
        for s in sorunlar:
            print(f"  - {s}")
    else:
        print("Tum sablonlar tutarli.")
