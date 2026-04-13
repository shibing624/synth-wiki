# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Pass 1: Extract and summarize sources with parallel LLM calls.
"""
from __future__ import annotations
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from synth_wiki.compiler.diff import SourceInfo
from synth_wiki.compiler.progress import phase_bar
from synth_wiki.extract import extract, is_image_source, chunk_if_needed
from synth_wiki.llm.client import Client, Message, CallOpts


@dataclass
class SummaryResult:
    source_path: str
    summary_path: str = ""
    summary: str = ""
    concepts: list[str] = field(default_factory=list)
    chunk_count: int = 0
    error: Optional[Exception] = None


def summarize(output_dir: str, sources: list[SourceInfo],
              client: Client, model: str, max_tokens: int, max_parallel: int = 4,
              language: str = "zh-CN") -> list[SummaryResult]:
    """Process sources through Pass 1."""
    results = [None] * len(sources)
    bar = phase_bar("Pass 1: Summarize", len(sources), unit="file")
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {}
        for i, src in enumerate(sources):
            f = pool.submit(summarize_one, output_dir, src, client, model, max_tokens, language, max_parallel)
            futures[f] = i
        for f in as_completed(futures):
            results[futures[f]] = f.result()
            bar.update(1)
    bar.close()
    return results


def summarize_one(output_dir: str, info: SourceInfo,
                  client: Client, model: str, max_tokens: int,
                  language: str = "zh-CN",
                  max_parallel: int = 4) -> SummaryResult:
    result = SummaryResult(source_path=info.path)
    lang_instruction = f" You MUST write ALL output in {language}."
    try:
        content = extract(info.path, info.type)

        if is_image_source(content):
            result.summary = "[Image source - requires vision LLM]"
            result.summary_path = _write_summary_file(output_dir, info, content.type, result.summary, 0)
            return result

        chunk_if_needed(content, max_tokens * 2)
        result.chunk_count = content.chunk_count

        if content.chunk_count <= 1:
            resp = client.chat_completion([
                Message(role="system", content="You are a research assistant creating structured summaries for a personal knowledge wiki." + lang_instruction),
                Message(role="user", content=f"Summarize this source document: {os.path.basename(info.path)}\n\n---\n\n{content.text}"),
            ], CallOpts(model=model, max_tokens=max_tokens))
            result.summary = resp.content
        else:
            chunk_results = [None] * len(content.chunks)
            with ThreadPoolExecutor(max_workers=min(len(content.chunks), max_parallel)) as chunk_pool:
                chunk_futures = {}
                for chunk in content.chunks:
                    f = chunk_pool.submit(
                        client.chat_completion,
                        [
                            Message(role="system", content="You are summarizing a section of a larger document." + lang_instruction),
                            Message(role="user", content=f"Summarize section {chunk.index+1} of {os.path.basename(info.path)}:\n\n{chunk.text}"),
                        ],
                        CallOpts(model=model, max_tokens=max_tokens // content.chunk_count),
                    )
                    chunk_futures[f] = chunk.index
                for f in chunk_futures:
                    chunk_results[chunk_futures[f]] = f.result().content

            combined = "\n\n---\n\n".join(chunk_results)
            resp = client.chat_completion([
                Message(role="system", content="You are synthesizing partial summaries into a final summary." + lang_instruction),
                Message(role="user", content=f"Combine these {len(chunk_results)} summaries of {os.path.basename(info.path)}:\n\n{combined}"),
            ], CallOpts(model=model, max_tokens=max_tokens))
            result.summary = resp.content

        result.summary_path = _write_summary_file(output_dir, info, content.type, result.summary, content.chunk_count)
    except (httpx.HTTPError, RuntimeError, IOError, json.JSONDecodeError) as e:
        result.error = e
    return result


def _write_summary_file(output_dir: str, info: SourceInfo,
                        source_type: str, summary: str, chunk_count: int) -> str:
    summary_dir = os.path.join(output_dir, "summaries")
    os.makedirs(summary_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(info.path))[0]
    abs_path = os.path.join(summary_dir, base + ".md")
    frontmatter = f"---\nsource: {info.path}\nsource_type: {source_type}\ncompiled_at: {datetime.now(timezone.utc).isoformat()}\nchunk_count: {chunk_count}\n---\n\n"
    with open(abs_path, "w") as f:
        f.write(frontmatter + summary)
    return abs_path
