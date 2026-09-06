"""Üreteç ile doğrulayıcı arasındaki bağımsızlık denetimi.

`generator.py` hataları kurar, `verifier.py` geçerliliği denetler. İkisi aynı kodu
paylaşırsa doğrulayıcı TANIM GEREĞİ %100 doğruluk alır — bu bir sonuç değil,
tanımın tekrarıdır (bkz. docs/taksonomi.md, başlık).

Ortak olan spesifikasyondur (docs/taksonomi.md), kod değildir.

Otomatik denetime bağlanmayan bir mimari kuralı üçüncü haftada kendiliğinden
ihlal edilir; bu test o yüzden vardır.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

#: Üretecin ASLA kullanmaması gereken modüller.
FORBIDDEN_FOR_GENERATOR = {"verifier", "theorems"}

#: Doğrulayıcının ASLA kullanmaması gereken modüller.
FORBIDDEN_FOR_VERIFIER = {"generator", "renderer"}


def _imported_module_names(path: Path) -> set[str]:
    """Bir dosyanın import ettiği modüllerin kök adlarını döndürür."""
    if not path.exists():
        return set()

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            # "from . import theorems" biçimi
            if node.level and node.level > 0:
                for alias in node.names:
                    names.add(alias.name.split(".")[0])

    return names


def _assert_clean(filename: str, forbidden: set[str]) -> None:
    path = SRC / filename
    if not path.exists():
        return  # dosya henüz yazılmadı; test ileride anlamlı olacak

    leaked = _imported_module_names(path) & forbidden
    assert not leaked, (
        f"{filename} şu modülleri import ediyor: {sorted(leaked)}. "
        f"Üreteç ile doğrulayıcı kod paylaşamaz — ortak olan yalnızca "
        f"docs/taksonomi.md spesifikasyonudur."
    )


def test_generator_does_not_import_verifier_side() -> None:
    _assert_clean("generator.py", FORBIDDEN_FOR_GENERATOR)


def test_verifier_does_not_import_generator_side() -> None:
    _assert_clean("verifier.py", FORBIDDEN_FOR_VERIFIER)


def test_verifier_never_reads_rendering_block() -> None:
    """Çizim bağlayıcı değildir: doğrulayıcı koordinatlara bakmamalıdır.

    `rendering` bloğuna erişim, sistemin "çizimde gerçekten dik mi?" diye
    sormaya başlaması demektir — projenin tüm dayanağı bunun tersidir.
    """
    path = SRC / "verifier.py"
    if not path.exists():
        return

    source = path.read_text(encoding="utf-8")
    for needle in ('"rendering"', "'rendering'", '"coords"', "'coords'"):
        assert needle not in source, (
            f"verifier.py içinde {needle} geçiyor. Doğrulayıcı yalnızca "
            f"figure ve steps alanlarını görmelidir; çizim bağlayıcı değildir."
        )
