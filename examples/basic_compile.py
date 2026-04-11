# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Basic synth-wiki compile example.

Usage:
    python examples/basic_compile.py

This creates a temporary project, adds sample documents, and shows
what the compile pipeline would do (dry run).
"""
import tempfile
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from synth_wiki.wiki import init_greenfield
from synth_wiki.compiler.pipeline import compile, CompileOpts


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = os.path.join(tmpdir, ".synth_wiki")
        source_dir = os.path.join(tmpdir, "raw")
        output_dir = os.path.join(tmpdir, "wiki")

        # Initialize project (isolated in tmpdir, no global config pollution)
        init_greenfield("example-wiki", source_dir, output_dir, home_dir=home_dir)
        config_path = os.path.join(home_dir, "config.yaml")
        print(f"Project initialized. Config: {config_path}")

        # Add sample documents
        with open(os.path.join(source_dir, "machine-learning.md"), "w") as f:
            f.write("# Machine Learning\n\nML is a subset of AI that enables systems to learn from data.\n")
        with open(os.path.join(source_dir, "neural-networks.md"), "w") as f:
            f.write("# Neural Networks\n\nNeural networks are computing systems inspired by biological neural networks.\n")

        print(f"Added 2 sample documents to {source_dir}")

        # Dry run compile
        result = compile("example-wiki", CompileOpts(dry_run=True, config_path=config_path))
        print(f"\nDry run results:")
        print(f"  Added: {result.added}")
        print(f"  Modified: {result.modified}")
        print(f"  Removed: {result.removed}")
        print(f"\nTo actually compile, set a real API key in config and remove --dry-run")


if __name__ == "__main__":
    main()
