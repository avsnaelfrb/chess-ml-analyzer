"""Entrypoint training model taktis pola serangan hitam.

    uv run python train_black_attack.py                 # sampel 200k, default
    uv run python train_black_attack.py --sample 0      # seluruh data
"""

from app.tactical_training import main

if __name__ == "__main__":
    raise SystemExit(main())
