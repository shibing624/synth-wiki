# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Progress display for compilation using tqdm.
"""
from __future__ import annotations

from tqdm import tqdm


def phase_bar(desc: str, total: int, unit: str = "item") -> tqdm:
    """Create a tqdm progress bar for a compilation phase."""
    return tqdm(total=total, desc=desc, unit=unit, dynamic_ncols=True,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]")
