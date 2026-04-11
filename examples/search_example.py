# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Search example with TreeSearch FTS5.

Usage:
    python examples/search_example.py

Demonstrates FTS5+vector hybrid search on an initialized project.
"""
import tempfile
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from synth_wiki.wiki import init_greenfield
from synth_wiki.storage import DB
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.vectors import Store as VectorStore
from synth_wiki.hybrid import Searcher, SearchOpts


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = os.path.join(tmpdir, ".synth_wiki")
        source_dir = os.path.join(tmpdir, "raw")
        output_dir = os.path.join(tmpdir, "wiki")
        init_greenfield("search-demo", source_dir, output_dir, home_dir=home_dir)

        db_path = os.path.join(home_dir, "db", "search-demo.db")
        db = DB.open(db_path)
        mem = MemoryStore(db_path)
        vec = VectorStore(db)

        mem.add(Entry(id="doc1", content="Machine learning uses algorithms to find patterns in data",
                      tags=["ml"], article_path="wiki/summaries/ml.md"))
        mem.add(Entry(id="doc2", content="Deep learning neural networks process complex data",
                      tags=["dl"], article_path="wiki/summaries/dl.md"))
        mem.add(Entry(id="doc3", content="Database query optimization for fast retrieval",
                      tags=["db"], article_path="wiki/summaries/db.md"))
        mem.add(Entry(id="doc4", content="机器学习是人工智能的一个重要分支领域",
                      tags=["ml"], article_path="wiki/summaries/ml_zh.md"))

        searcher = Searcher(mem, vec)

        print("Search results for 'machine learning algorithms':")
        results = searcher.search(SearchOpts(query="machine learning algorithms"))
        for r in results:
            print(f"  [{r.score:.4f}] {r.id}: {r.content[:60]}...")

        print("\nSearch results for '机器学习' (Chinese):")
        results = searcher.search(SearchOpts(query="机器学习"))
        for r in results:
            print(f"  [{r.score:.4f}] {r.id}: {r.content[:60]}...")

        mem.close()
        db.close()


if __name__ == "__main__":
    main()
