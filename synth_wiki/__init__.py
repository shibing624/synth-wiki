# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: synth-wiki: AI-powered wiki compiler.

Usage:
    from synth_wiki import Config, load_config, compile, Searcher
    cfg = load_config("~/.synth_wiki/config.yaml", "my-project")
    result = compile("my-project")
"""
__version__ = "0.1.3"

# --- Core public API ---
from synth_wiki.config import Config, load as load_config, load_global as load_global_config, list_projects
from synth_wiki.compiler.pipeline import compile, CompileOpts, CompileResult
from synth_wiki.hybrid import Searcher, SearchOpts, SearchResult
from synth_wiki.llm.client import Client, Message, CallOpts, Usage, Response
from synth_wiki.llm.cost import CostTracker, CostReport
from synth_wiki.storage import DB

__all__ = [
    "__version__",
    # config
    "Config", "load_config", "load_global_config", "list_projects",
    # compiler
    "compile", "CompileOpts", "CompileResult",
    # search
    "Searcher", "SearchOpts", "SearchResult",
    # llm
    "Client", "Message", "CallOpts", "Usage", "Response",
    "CostTracker", "CostReport",
    # storage
    "DB",
]
