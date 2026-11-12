"""Exercise launcher preflight failures without starting/stopping the user's server."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell launcher")


def test_explicit_missing_model_fails_without_silent_fallback(tmp_path):
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(ROOT / "iniciar.ps1"),
         "-Modelo", str(tmp_path / "missing.pt"), "-Verificar"],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert "No se encontraron los pesos" in result.stdout
    assert "Compilando" not in result.stdout


def test_invalid_port_is_rejected_before_startup():
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(ROOT / "iniciar.ps1"), "-Puerto", "0"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "Preparando la estacion" not in result.stdout
