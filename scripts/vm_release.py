"""Run the shared version manager without rewriting historical documentation."""
import argparse
import importlib.util
import sys
from pathlib import Path

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--vm", required=True, type=Path)
args, forwarded = parser.parse_known_args()
entry = args.vm.resolve(strict=True)
spec = importlib.util.spec_from_file_location("shared_version_manager", entry)
if spec is None or spec.loader is None:
    raise SystemExit(f"Could not load version manager: {entry}")
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

# VERSION and CHANGELOG are managed by the shared tool. Keep its automatic
# version replacement out of current and historical product documentation.
manager.update_version_in_files = lambda old_version, new_version, dry_run=False: []
sys.argv = [str(entry), *forwarded]
manager.main()
