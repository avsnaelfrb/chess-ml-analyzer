"""Entrypoint training model (pasangan `main.py` yang untuk server).

Latih model klasifikasi fase dari FEN:

    uv run python train.py                       # sampel 200k, default
    uv run python train.py --sample 0            # seluruh dataset
"""

from app.ml import main

if __name__ == "__main__":
    raise SystemExit(main())