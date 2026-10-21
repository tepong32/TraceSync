"""Generate an external temporary spec and build the acceptance-only cache artifact."""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys


BASE_COMMIT = "3996629a9cce7a7421fe000d1008a60c5dc430b6"
PRODUCTION_HASH = "95b3553265a23e4018b9e03a88525b5f74f4692a008e85f121d6a293a719dbbe"


def acceptance_spec(text, repo):
    absolute_datas = [(str(repo / "assets"), "assets"), (str(repo / "VERSION"), ".")]
    changes = {
        "['main.py']": repr([str(repo / "main.py")]),
        "pathex=[]": "pathex=" + repr([str(repo)]),
        "datas=[('assets', 'assets'), ('VERSION', '.')]": "datas=" + repr(absolute_datas),
        "runtime_hooks=[]": "runtime_hooks=" + repr([str(repo / "acceptance/cache_runtime_hook.py")]),
        "name='TraceSync'": "name='TraceSync-Cache-Acceptance'",
        "console=False": "console=True",
        "icon=['assets\\\\icons\\\\tracesync.png']": "icon=" + repr([str(repo / "assets/icons/tracesync.png")]),
    }
    for old, new in changes.items():
        if text.count(old) != 1:
            raise ValueError("Production spec changed; review required: " + old)
        text = text.replace(old, new)
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = args.output
    if not output.is_absolute() or output.exists() or ".." in output.parts:
        raise ValueError("Choose a new absolute external output directory")
    if output.resolve().is_relative_to(repo):
        raise ValueError("Build output must be outside repository")
    git = lambda *a: subprocess.check_output(["git", "-C", str(repo), *a], text=True).strip()
    if git("rev-parse", "HEAD") != BASE_COMMIT:
        raise ValueError("Unexpected checkpoint")
    if git("diff", "HEAD", "--", "core", "models", "ui", "utils", "main.py", "TraceSync.spec", "requirements.txt"):
        raise ValueError("Production inputs changed")
    tools = {p: version(p) for p in ("pyinstaller", "pyinstaller-hooks-contrib", "setuptools")}
    if tools != {"pyinstaller": "6.22.3", "pyinstaller-hooks-contrib": "2026.7", "setuptools": "78.1.1"}:
        raise ValueError("Unexpected builder versions")
    spec = acceptance_spec((repo / "TraceSync.spec").read_text(), repo)
    output.mkdir(parents=True)
    spec_path = output / "TraceSync-Cache-Acceptance.spec"
    spec_path.write_text(spec, encoding="utf-8")
    env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(output / "pyinstaller-cache"), PYTHONDONTWRITEBYTECODE="1")
    with (output / "build.log").open("w", encoding="utf-8") as log:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath",
                        str(output / "dist"), "--workpath", str(output / "work"), str(spec_path)],
                       cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    artifact = output / "dist/TraceSync-Cache-Acceptance.exe"
    sources = [*sorted((repo / "acceptance").glob("*.py")), Path(__file__), repo / "TraceSync.spec", repo / "core/onedrive_auth.py"]
    manifest = {"base_commit": BASE_COMMIT, "uncommitted_diagnostic": True, "python": sys.version,
                "tools": tools, "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "source_sha256": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                "temporary_spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
                "production_artifact_sha256": PRODUCTION_HASH}
    (output / "BUILD-INFO.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
