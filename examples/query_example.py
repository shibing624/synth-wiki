# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: RAG query example.

Usage:
    python examples/query_example.py

Demonstrates querying a synth-wiki knowledge base.
Note: Requires a configured API key for actual LLM calls.
"""
import tempfile
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from synth_wiki.wiki import init_greenfield, get_status, format_status


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = os.path.join(tmpdir, ".synth_wiki")
        source_dir = os.path.join(tmpdir, "raw")
        output_dir = os.path.join(tmpdir, "wiki")
        init_greenfield("query-demo", source_dir, output_dir, home_dir=home_dir)

        config_path = os.path.join(home_dir, "config.yaml")
        # Show status
        info = get_status("query-demo", config_path=config_path, home_dir=home_dir)
        print(format_status(info))
        print("\nTo query the wiki, add documents, compile, then use:")
        print("  synth-wiki --project query-demo search 'What is machine learning?'")
        print(f"\nThis requires a configured LLM provider in {config_path}")


if __name__ == "__main__":
    main()
