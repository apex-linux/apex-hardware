"""Enforces the import rules between the layers of src/apex_hw."""

import ast
import pathlib
import unittest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "apex_hw"

# Which layers each layer may import. Entry points may import anything.
ALLOWED = {
    "kernel": {"kernel"},
    "platform": {"platform"},
    "checks": {"checks", "kernel", "platform"},
    "testkit": {"testkit", "platform", "kernel"},
}


def _imported_layers(path: pathlib.Path) -> set[str]:
    """Returns the apex_hw layers that a module imports."""
    layers = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            parts = name.split(".")
            if parts[0] == "apex_hw" and len(parts) > 1:
                layers.add(parts[1])
    return layers


class LayersTest(unittest.TestCase):

    def test_layers_import_only_what_they_may(self) -> None:
        for layer, allowed in ALLOWED.items():
            for path in sorted((SRC / layer).glob("*.py")):
                with self.subTest(module=f"{layer}/{path.name}"):
                    self.assertLessEqual(_imported_layers(path), allowed)

    def test_only_entry_points_use_the_linux_adapter(self) -> None:
        for path in sorted(SRC.rglob("*.py")):
            if path.parent.name in ("entrypoints", "platform"):
                continue
            with self.subTest(module=str(path.relative_to(SRC))):
                self.assertNotIn("LinuxHost", path.read_text(encoding="utf-8"))
