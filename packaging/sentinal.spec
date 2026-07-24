# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds the self-contained one-file `sentinal` Linux binary.

Run from the repo root (packaging/build_binary.sh does this for you):

    pyinstaller packaging/sentinal.spec --distpath dist --workpath build/pyi --noconfirm

Read-only shipped artifacts are bundled so the binary needs nothing on disk:

    model/artifacts/                        -> artifacts/            (ONNX embedding model, pretrained joblib models, drain3 seed states)
    model/vibesentinel_model/drain3_config.ini -> vibesentinel_model/
    dashboard/dist/                         -> dashboard/dist/       (built UI)

vibesentinel_model._resources and sentinal._resources resolve these from
sys._MEIPASS at runtime. Per-target state (a target's own trained model, live
drain3 state) is written to the user data dir instead, never into the bundle.

The ONNX model must already be exported into model/artifacts/all-MiniLM-L6-v2/
before building (build_binary.sh runs model/scripts/export_onnx_model.py first).
Torch/transformers/optimum are excluded — they're only needed for that export
step, not at detection runtime.
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = Path(os.getcwd())

_onnx_dir = ROOT / "model" / "artifacts" / "all-MiniLM-L6-v2"
if not (_onnx_dir / "model.onnx").exists():
    raise SystemExit(
        f"ONNX model not found at {_onnx_dir}/model.onnx — run "
        "`python model/scripts/export_onnx_model.py` before building the binary."
    )

datas = [
    (str(ROOT / "model" / "artifacts"), "artifacts"),
    (str(ROOT / "model" / "vibesentinel_model" / "drain3_config.ini"), "vibesentinel_model"),
    (str(ROOT / "dashboard" / "dist"), "dashboard/dist"),
    # Hosted platform (`sentinal core`) host-side assets — env-image build
    # context + demo scripts. Resolved via vibesentinel_core._resources.
    (str(ROOT / "backend" / "vibesentinel_core" / "env_image"), "vibesentinel_core/env_image"),
    (str(ROOT / "backend" / "vibesentinel_core" / "demo_assets"), "vibesentinel_core/demo_assets"),
]
binaries = []
hiddenimports = []

# These ship data files / native libs / dynamically-imported submodules that
# PyInstaller's static analysis alone doesn't fully catch.
for pkg in ("onnxruntime", "sklearn", "scipy", "drain3", "tokenizers"):
    datas += collect_data_files(pkg)
for pkg in ("onnxruntime", "sklearn", "scipy", "numpy"):
    binaries += collect_dynamic_libs(pkg)
for pkg in ("sklearn", "scipy", "onnxruntime", "uvicorn", "drain3",
            "vibesentinel_core", "fastapi", "starlette", "websockets"):
    hiddenimports += collect_submodules(pkg)

excludes = [
    "torch", "transformers", "optimum",  # export-only, huge
    "matplotlib", "pandas", "IPython", "notebook", "jupyter",
    "tkinter", "PyQt5", "PySide2",
]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "cli"), str(ROOT / "model"), str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

# One-file: passing binaries + datas straight to EXE (no COLLECT) makes the
# bootloader self-extract to a temp dir (sys._MEIPASS) at startup.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sentinal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
)
