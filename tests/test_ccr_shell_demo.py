"""F23/F24 PoC smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from llove.demo.ccr_shell_demo import CcrShellDemoApp


def test_app_constructs() -> None:
    app = CcrShellDemoApp()
    assert app._cwd == Path.cwd()
    assert "F23/F24" in app.TITLE or "llove" in app.TITLE
    assert app._output is None  # compose() で生成されるので mount 前は None


def test_app_has_required_bindings() -> None:
    app = CcrShellDemoApp()
    keys = [b.key if hasattr(b, "key") else b[0] for b in app.BINDINGS]
    assert "q" in keys
    assert "ctrl+l" in keys
    assert "ctrl+c" in keys


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell on Windows only")
def test_powershell_available() -> None:
    """smoke: pwsh or powershell が PATH 上にある (Windows 開発機の前提)."""
    import shutil

    ps = shutil.which("pwsh") or shutil.which("powershell")
    assert ps is not None, "PowerShell が PATH に見つからない (Windows での前提)"
