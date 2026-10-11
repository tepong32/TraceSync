"""Run the shared version manager without rewriting historical documentation."""
import argparse
import runpy
import sys
from pathlib import Path

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--vm", required=True, type=Path)
args, forwarded = parser.parse_known_args()
entry = args.vm.resolve(strict=True)
sys.path.insert(0, str(entry.parent))
from version_manager.documentation import DocumentationUpdater

# VERSION and CHANGELOG are managed by the shared tool. Current release prose
# is reviewed explicitly; archived screenshots and historical versions stay intact.
DocumentationUpdater._version_targets = lambda self: []
sys.argv = [str(entry), *forwarded]
runpy.run_path(str(entry), run_name="__main__")
