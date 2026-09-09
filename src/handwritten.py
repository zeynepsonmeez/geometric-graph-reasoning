"""Elle yazılan kümenin yüklenmesi, denetimi ve çizimi.

Bu küme sentetik derleme **karıştırılmaz**; ayrı tutulmuş bir değerlendirme
kümesidir (bkz. data/handwritten/README.md).

Körlük dosya düzeniyle sağlanır:

    solutions/   çözümler, ETİKETSİZ
    labels/      etiketler, kodlayıcı başına ayrı dosya

Çözüm dosyalarında `label` alanı bulunmaz ve şema bunu reddeder. İkinci kodlayıcı
birincinin kararını teknik olarak göremez.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path
from typing import Any

import renderer

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "handwritten"
SOLUTIONS_DIR = BASE / "solutions"
LABELS_DIR = BASE / "labels"
SOLUTION_SCHEMA = ROOT / "schema" / "solution.schema.json"

#: Biçim örnekleri kümenin parçası değildir.
SKIP_PREFIX = "ORNEK-"

VALID_CLASSES = ("H0", "H1", "H2", "H3")


# --------------------------------------------------------------------------
# Şema
# --------------------------------------------------------------------------


def unlabeled_schema() -> dict[str, Any]:
    """Çözüm şemasının etiketsiz sürümü.

    Ayrı bir dosya olarak kopyalanmaz; tek kaynaktan türetilir ki iki şema
    zamanla birbirinden ayrışmasın. `label` yalnızca isteğe bağlı olmaz,
    tümüyle YASAKLANIR — etiketin çözüm dosyasına sızması körlüğü bozar.
    """
    schema = json.loads(SOLUTION_SCHEMA.read_text(encoding="utf-8"))
    schema["required"] = [r for r in schema["required"] if r != "label"]
    schema["properties"].pop("label", None)
    schema["properties"]["_aciklama"] = {"type": "string"}
    # rendering.coords elle yazılmaz; --render ile doldurulur
    schema["properties"]["rendering"]["required"] = ["bias"]
    return schema


# --------------------------------------------------------------------------
# Yükleme
# --------------------------------------------------------------------------


def solution_paths() -> list[Path]:
    if not SOLUTIONS_DIR.exists():
        return []
    return sorted(
        p for p in SOLUTIONS_DIR.glob("*.json") if not p.name.startswith(SKIP_PREFIX)
    )


def load_solutions() -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in solution_paths()]


def load_labels(coder: str) -> dict[str, dict[str, Any]]:
    """Bir kodlayıcının etiketleri: problem_id → {error_class, error_step}."""
    path = LABELS_DIR / f"{coder}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Denetim
# --------------------------------------------------------------------------


def check(solutions: list[dict[str, Any]] | None = None) -> list[str]:
    """Şema uyumu ve iç tutarlılık; sorun listesi döndürür (boşsa temiz)."""
    solutions = load_solutions() if solutions is None else solutions
    problems: list[str] = []

    try:
        import jsonschema
    except ImportError:
        jsonschema = None
        problems.append("uyari: jsonschema kurulu degil, sema denetimi atlandi")

    schema = unlabeled_schema()
    gorulen: set[str] = set()

    for sol in solutions:
        pid = sol.get("problem_id", "?")

        if pid in gorulen:
            problems.append(f"{pid}: yinelenen problem_id")
        gorulen.add(pid)

        if "label" in sol:
            problems.append(
                f"{pid}: cozum dosyasinda 'label' var. Etiketler labels/ altinda "
                f"tutulur; burada bulunmasi korlugu bozar."
            )

        if jsonschema is not None:
            try:
                jsonschema.validate(sol, schema)
            except jsonschema.ValidationError as e:
                yol = "/".join(str(x) for x in e.absolute_path) or "(kok)"
                problems.append(f"{pid}: sema hatasi @ {yol}: {e.message}")
                continue

        # Şema boş dizeyi kabul eder; yarım kalmış iskeletin "tutarlı" görünmesini
        # engellemek için içerik doluluğu ayrıca denetlenir.
        if not (sol.get("soru") or "").strip():
            problems.append(f"{pid}: 'soru' bos — ornek henuz doldurulmamis")

        gorulen_adim: set[str] = set()
        for step in sol.get("steps", []):
            if not (step.get("rule") or "").strip():
                problems.append(f"{pid}/{step.get('id', '?')}: 'rule' bos")
            if not (step.get("claim") or "").strip():
                problems.append(f"{pid}/{step.get('id', '?')}: 'claim' bos")
            for dep in step.get("depends_on", []):
                if dep not in gorulen_adim:
                    problems.append(
                        f"{pid}/{step['id']}: '{dep}' adimina bagli ama o adim sonra geliyor"
                    )
            gorulen_adim.add(step["id"])

            if step.get("rule") == "verilen" and not (step.get("refs") or {}).get("asserts"):
                problems.append(
                    f"{pid}/{step['id']}: 'verilen' adiminda refs.asserts eksik. "
                    f"Dogrulayici neyin verilmis sayildigini bilemez."
                )

    return problems


def check_labels() -> list[str]:
    """Etiket dosyalarını çözümlerle karşılaştırır."""
    problems: list[str] = []
    ids = {s["problem_id"] for s in load_solutions()}

    for coder in ("A1", "A2"):
        labels = load_labels(coder)
        if not labels:
            continue
        for pid, lab in labels.items():
            if pid not in ids:
                problems.append(f"{coder}: '{pid}' icin cozum dosyasi yok")
            sinif = lab.get("error_class")
            if sinif not in VALID_CLASSES:
                problems.append(f"{coder}/{pid}: gecersiz sinif '{sinif}'")
            if sinif == "H0" and lab.get("error_step") is not None:
                problems.append(f"{coder}/{pid}: H0 icin error_step null olmali")
            if sinif != "H0" and not lab.get("error_step"):
                problems.append(f"{coder}/{pid}: hata sinifinda error_step zorunlu")

    return problems


# --------------------------------------------------------------------------
# Çizim
# --------------------------------------------------------------------------


def fill_rendering(solution: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    """`rendering.coords` alanını çizim motoruyla doldurur.

    Koordinatlar elle yazılmaz. Verilen nitel ilişkiler birebir doğru çizilir;
    `bias` yalnızca VERİLMEMİŞ nicelikleri etkiler (docs/taksonomi.md §1).
    """
    sol = copy.deepcopy(solution)
    rendering = sol.setdefault("rendering", {})
    bias = rendering.get("bias", "neutral")

    rng = random.Random(seed if seed is not None else hash(sol["problem_id"]) & 0xFFFF)
    rendering["coords"] = renderer.layout(sol["figure"], bias, rendering.get("cizim_ipucu"), rng)
    rendering.setdefault("note", "Şekil ölçekli değildir.")
    rendering.pop("cizim_ipucu", None)
    return sol


def render_all() -> int:
    sayac = 0
    for path in solution_paths():
        sol = json.loads(path.read_text(encoding="utf-8"))
        dolu = fill_rendering(sol)
        path.write_text(
            json.dumps(dolu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        sayac += 1
    return sayac


# --------------------------------------------------------------------------
# İskelet
# --------------------------------------------------------------------------

ISKELET: dict[str, Any] = {
    "problem_id": "EL-0000",
    "family": "P3",
    "kazanim_kodu": None,
    "soru": "",
    "figure": {
        "points": ["A", "B", "C"],
        "segments": [
            {"from": "A", "to": "B", "type": "side", "length": None},
            {"from": "B", "to": "C", "type": "side", "length": None},
            {"from": "A", "to": "C", "type": "side", "length": None},
        ],
        "angles": [],
        "perpendicular": [],
        "congruent_segments": [],
        "similar": [],
    },
    "rendering": {"bias": "neutral", "note": "Şekil ölçekli değildir."},
    "steps": [
        {"id": "s1", "claim": "", "rule": "", "depends_on": [], "refs": {}},
    ],
}


def scaffold(problem_id: str) -> Path:
    SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SOLUTIONS_DIR / f"{problem_id}.json"
    if path.exists():
        raise FileExistsError(f"{path} zaten var")

    sol = copy.deepcopy(ISKELET)
    sol["problem_id"] = problem_id
    path.write_text(json.dumps(sol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Elle yazilan kume araclari")
    parser.add_argument("--check", action="store_true", help="sema ve tutarlilik denetimi")
    parser.add_argument("--render", action="store_true", help="rendering.coords doldur")
    parser.add_argument("--new", metavar="ID", help="bos ornek dosyasi olustur, orn. EL-0001")
    args = parser.parse_args()

    if args.new:
        print("olusturuldu:", scaffold(args.new).relative_to(ROOT))
        return

    if args.render:
        print(f"{render_all()} dosyanin koordinatlari guncellendi")
        return

    solutions = load_solutions()
    print(f"{len(solutions)} cozum yuklendi (hedef: 30)")

    sorunlar = check(solutions) + check_labels()
    if sorunlar:
        print(f"\n{len(sorunlar)} sorun:")
        for s in sorunlar:
            print(f"  - {s}")
    elif solutions:
        print("Tum cozumler tutarli.")

    for coder in ("A1", "A2"):
        n = len(load_labels(coder))
        print(f"  {coder} etiketi: {n}/{len(solutions)}")


if __name__ == "__main__":
    main()
