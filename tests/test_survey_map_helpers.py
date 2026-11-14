"""Exercise native, Termux and Cygwin map dispatch without requiring those hosts."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def executable(path, body):
    """Write an invented executable into an isolated test directory.

    Args:
        path: Temporary executable filename, potentially containing spaces.
        body: Python statements executed after an interpreter-specific shebang.

    Returns:
        Path to an executable stub that never runs real R or proot.
    """
    path.write_text(f"#!{sys.executable}\n{body}\n")
    path.chmod(0o755)
    return path


@pytest.mark.parametrize("platform", ["Linux", "CYGWIN_NT-10.0", "Termux"])
def test_platform_argument_vectors_are_safe(tmp_path, platform):
    """Preserve paths and choose the approved platform runtime automatically.

    Args:
        tmp_path: Temporary bundle, fake tools and captured command output.
        platform: Synthetic native, Windows/Cygwin or Android environment.

    Returns:
        None. Quoted arguments survive dispatch and Windows IDEs are never launched.
    """
    tools = tmp_path / "bin"
    tools.mkdir()
    bundle = tmp_path / "maps with 'quotes' and č"
    bundle.mkdir()
    (bundle / "input-manifest.json").write_text(json.dumps({"kind": "so2"}))
    log = tmp_path / "args.json"
    body = "import os,sys,json; open(os.environ['CAPTURE'],'w').write(json.dumps(sys.argv[1:]))"
    r = executable(tools / ("Rscript.exe" if platform.startswith("CYGWIN") else "Rscript"), body)
    executable(tools / "uname", f"print({('Linux' if platform == 'Termux' else platform)!r})")
    executable(tools / "cygpath", "import sys; print(sys.argv[-1] if '-u' in sys.argv else 'WIN:' + sys.argv[-1])")
    executable(tools / "proot-distro", body)
    env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"], "CAPTURE": str(log), "PREFIX": "/usr"}
    env.pop("TERMUX_VERSION", None)
    env.pop("RSCRIPT", None)
    if platform == "Termux":
        env["TERMUX_VERSION"] = "fixture"
    result = subprocess.run(["bash", str(ROOT / "scripts/render-so2-maps.sh"), "--overwrite", str(bundle)],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    args = json.loads(log.read_text())
    assert any(str(bundle) in arg for arg in args)
    assert "--overwrite" in args and "--kind=so2" in args
    if platform == "Termux":
        assert args[:2] == ["login", "debian"] and "--bind" in args
    elif platform.startswith("CYGWIN"):
        assert args[0].startswith("WIN:")
    assert r.exists()


def test_kind_mismatch_and_renderer_failure_do_not_publish(tmp_path):
    """Reject wrong bundles and preserve original outputs when a renderer fails.

    Args:
        tmp_path: Isolated bundle and executable capture directory.

    Returns:
        None. Kind mismatch never starts R; genuine renderer exit codes propagate.
    """
    bundle = tmp_path / "maps"
    bundle.mkdir()
    (bundle / "input-manifest.json").write_text('{"kind":"mucp"}')
    sentinel = bundle / "old.pdf"
    sentinel.write_bytes(b"sentinel")
    runtime = executable(tmp_path / "my Rscript", "import sys; sys.exit(7)")
    for kind, expected in (("so2", 2), ("mucp", 7)):
        result = subprocess.run(["bash", str(ROOT / f"scripts/render-{kind}-maps.sh"),
                                 "--rscript", str(runtime), str(bundle)], capture_output=True, text=True,
                                env={**os.environ, "TERMUX_VERSION": "", "PREFIX": "/usr"})
        assert result.returncode == expected, result.stderr
        assert sentinel.read_bytes() == b"sentinel"


@pytest.mark.parametrize("discovery", ["home", "programfiles", "explicit", "environment", "missing"])
def test_cygwin_discovery_and_precedence(tmp_path, discovery):
    """Check automatic Windows runtime selection without launching an IDE.

    Args:
        tmp_path: Isolated Windows-drive mapping, stubs and argument capture files.
        discovery: Runtime source or absent-runtime path being exercised.

    Returns:
        None. Explicit overrides win, versions sort numerically and errors stay clear.
    """
    tools = tmp_path / "bin"
    tools.mkdir()
    bundle = tmp_path / "-maps"
    bundle.mkdir()
    (bundle / "input-manifest.json").write_text('{"kind":"mucp"}')
    drive = tmp_path / "D Drive"
    log = tmp_path / "runtime"
    body = "import os,sys; open(os.environ['CAPTURE'],'w').write(sys.argv[0])"
    home = drive / "home R" / "bin"
    home.mkdir(parents=True)
    executable(home / "Rscript.exe", body)
    for version in ("4.9.0", "4.10.0"):
        folder = drive / "Program Files" / "R" / ("R-" + version) / "bin"
        folder.mkdir(parents=True)
        executable(folder / "Rscript.exe", body)
    override = executable(tools / "explicit R", body)
    executable(tools / "uname", "print('CYGWIN_NT-10.0')")
    executable(tools / "cygpath", "import sys,os; print(sys.argv[-1].replace('D:',os.environ['DRIVE']).replace(chr(92),'/'))")
    env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"], "CAPTURE": str(log),
           "DRIVE": str(drive), "PROGRAMFILES": r"D:\Program Files", "PREFIX": "/usr"}
    for name in ("R_HOME", "RSCRIPT", "TERMUX_VERSION"):
        env.pop(name, None)
    arguments = []
    if discovery == "home":
        env["R_HOME"] = r"D:\home R"
    elif discovery == "explicit":
        env["RSCRIPT"] = str(tools / "does-not-exist")
        arguments = ["--rscript", str(override)]
    elif discovery == "environment":
        env["RSCRIPT"] = str(override)
    elif discovery == "missing":
        env["PROGRAMFILES"] = r"D:\Absent"
    result = subprocess.run(["bash", str(ROOT / "scripts/render-mucp-maps.sh"), *arguments, "--", bundle.name],
                            env=env, cwd=tmp_path, capture_output=True, text=True)
    if discovery == "missing":
        assert result.returncode == 2 and "Rscript.exe not found" in result.stderr
        assert not log.exists()
    else:
        assert result.returncode == 0, result.stderr
        selected = log.read_text()
        assert ("home R" if discovery == "home" else "4.10.0" if discovery == "programfiles" else "explicit R") in selected


@pytest.mark.parametrize("termux", [False, True])
def test_missing_host_runtime_is_actionable_and_preserves_outputs(tmp_path, termux):
    """Exercise absent native R and absent Termux proot without relying on host PATH.

    Args:
        tmp_path: Isolated executable search path, prepared bundle and old output.
        termux: Whether the helper should require Debian proot rather than native R.

    Returns:
        None. Both failures name the missing runtime and leave old bytes intact.
    """
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "python3").symlink_to(sys.executable)
    (tools / "dirname").symlink_to(shutil.which("dirname"))
    executable(tools / "uname", "print('Linux')")
    bundle = tmp_path / "maps"
    bundle.mkdir()
    (bundle / "input-manifest.json").write_text('{"kind":"so2"}')
    (bundle / "sentinel.pdf").write_bytes(b"old")
    env = {**os.environ, "PATH": str(tools), "PREFIX": "/usr"}
    env.pop("RSCRIPT", None)
    env.pop("TERMUX_VERSION", None)
    if termux:
        env["TERMUX_VERSION"] = "fixture"
    result = subprocess.run([shutil.which("bash"), str(ROOT / "scripts/render-so2-maps.sh"), str(bundle)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert ("Termux requires proot-distro" if termux else "Rscript not found") in result.stderr
    assert (bundle / "sentinel.pdf").read_bytes() == b"old"
