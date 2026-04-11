# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Pass 4: Image handling.

Images are processed inline during Pass 1 (summarize) via vision LLM.
This pass logs a summary of image sources found.
"""
from __future__ import annotations

from synth_wiki import log
from synth_wiki.compiler.diff import SourceInfo


def extract_images(output_dir: str, sources: list[SourceInfo] | None) -> None:
    """Run Pass 4: image handling.

    Images are processed inline during Pass 1 via vision LLM.
    This pass logs a summary of image sources found.
    """
    if not sources:
        return
    image_count = sum(1 for s in sources if s.type == "image")
    if image_count > 0:
        log.info("Pass 4: image sources processed via vision in Pass 1", image_sources=image_count)
