#!/bin/bash
# Create .venv in this checkout with what mmBench needs, and check the system tools.
#
#   bash install.sh             # openai, httpx, Pillow (+ matplotlib for the report's chart)
#   MMB_MIRROR=cn bash install.sh   # packages from a mirror in China (BFSU)
#
# Uses uv when it is on PATH, else python3 -m venv + pip. Python 3.10 or newer.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
[ "${MMB_MIRROR:-}" = cn ] && export UV_INDEX_URL=https://mirrors.bfsu.edu.cn/pypi/web/simple \
  PIP_INDEX_URL=https://mirrors.bfsu.edu.cn/pypi/web/simple
if command -v uv >/dev/null; then
  uv venv -q --allow-existing -p 3.12 .venv
  VIRTUAL_ENV=$PWD/.venv uv pip install -q --no-config -r requirements.txt
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -r requirements.txt
fi
.venv/bin/python -c "import openai, httpx, PIL; print('python packages ok: openai', openai.__version__, '| Pillow', PIL.__version__)"
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && echo "ffmpeg ok" \
  || echo "ffmpeg missing: install it (e.g. apt-get install ffmpeg) before building the video items"
command -v xelatex >/dev/null && echo "xelatex ok (PDF reports)" || echo "no xelatex: reports come as Markdown and LaTeX source"
