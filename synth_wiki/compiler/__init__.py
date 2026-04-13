# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Compiler pipeline for synth-wiki.
"""
__version__ = '0.1.3'

from synth_wiki.compiler.pipeline import compile, CompileOpts, CompileResult
from synth_wiki.compiler.diff import diff, DiffResult, SourceInfo
from synth_wiki.compiler.summarize import summarize, SummaryResult
from synth_wiki.compiler.concepts import extract_concepts, ExtractedConcept
from synth_wiki.compiler.write import write_articles, ArticleResult
from synth_wiki.compiler.synthesize import generate_syntheses, SynthesisResult
from synth_wiki.compiler.overview import generate_overview
from synth_wiki.compiler.archive import archive_query
