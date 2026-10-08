"""One-command reproduction:  python -m src.run_all  [--skip-notebook]

1. executes notebooks/earthquake_damage.ipynb top-to-bottom in a fresh kernel (writes
   figures/, outputs/results.json, outputs/submission.csv and saves the outputs in-place);
2. builds report/report.docx (+ report.pdf when Microsoft Word is available);
3. builds slides/presentation.pptx and slides/speaker_notes.md.
"""
import argparse
import os
import sys
import time

from .data import ROOT


def execute_notebook(path):
    import nbformat
    from nbclient import NotebookClient

    if sys.platform == "win32":  # pyzmq + Proactor loop warning on Windows
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    os.environ.setdefault("PYTHONPATH", str(ROOT))
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, timeout=7200, kernel_name="python3",
                   resources={"metadata": {"path": str(path.parent)}}).execute()
    nbformat.write(nb, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-notebook", action="store_true",
                    help="reuse existing outputs/results.json and figures")
    args = ap.parse_args()
    t0 = time.time()
    if not args.skip_notebook:
        print("[1/3] executing notebook (about 25-75 min) ...", flush=True)
        execute_notebook(ROOT / "notebooks" / "earthquake_damage.ipynb")
    from . import build_report, build_slides
    print("[2/3] building report ...", flush=True)
    build_report.main()
    print("[3/3] building slides ...", flush=True)
    build_slides.main()
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
