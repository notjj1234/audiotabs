"""Mel-Band RoFormer model code from ZFTurbo/Music-Source-Separation-Training (MIT, see LICENSE).

Copied from models/bs_roformer/{mel_band_roformer,attend}.py on 2026-11-25. Only the
import of ``Attend`` was changed. This version honours ``mlp_expansion_factor`` and
``skip_connection``, which the Lead/Rhythm checkpoint needs; the pip packages do not.
"""

REQUIRED_MODULES = ("torch", "einops", "beartype", "rotary_embedding_torch", "librosa")
