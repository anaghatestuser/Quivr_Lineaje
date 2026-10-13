# Copyright (c) Lineaje, Inc. All rights reserved.
# Lineaje UnifAI guardrail  version=2.0.0-alpha
def _lineaje_load_gr_client():
    """Lineaje-added: load gr_stub_client.py without a pip dependency."""
    import sys as _s, importlib.util as _ilu
    from pathlib import Path as _P
    n = "_lineaje_gr_stub_client"
    if n in _s.modules: return _s.modules[n]
    h = _P(__file__).resolve().parent
    _cand = next((d / "gr_stub_client.py" for d in [h, *h.parents][:8] if (d / "gr_stub_client.py").is_file()), h / "gr_stub_client.py")
    _spec = _ilu.spec_from_file_location(n, _cand)
    _s.modules[n] = _m = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_m); return _m
def _lineaje_current_model():
    """Lineaje-added: reread the app's model setting for every request."""
    import os as _o
    from pathlib import Path as _P
    _keys = ("OPENROUTER_MODEL", "LLM_MODEL", "MODEL_NAME", "MODEL_ID", "OPENAI_MODEL", "ANTHROPIC_MODEL", "BEDROCK_MODEL_ID")
    _here = _P(__file__).resolve().parent
    for _path in (_here / ".env", *(_p / ".env" for _p in list(_here.parents)[:8])):
        if not _path.is_file(): continue
        try: _lines = _path.read_text(encoding="utf-8").splitlines()
        except OSError: continue
        _values = {}
        for _line in _lines:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line: continue
            _key, _, _value = _line.partition("=")
            if _key.strip() in _keys: _values[_key.strip()] = _value.strip().strip(chr(34)).strip(chr(39))
        for _key in _keys:
            if _values.get(_key): return _values[_key]
    return next((_o.environ[_key].strip() for _key in _keys if _o.environ.get(_key, "").strip()), "")

import asyncio
import logging
import os
from pathlib import Path

import dotenv
from quivr_core import Brain
from quivr_core.rag.entities.config import AssistantConfig
from rich.traceback import install as rich_install

ConsoleOutputHandler = logging.StreamHandler()

logger = logging.getLogger("quivr_core")
logger.setLevel(logging.DEBUG)
logger.addHandler(ConsoleOutputHandler)


logger = logging.getLogger("megaparse")
logger.setLevel(logging.DEBUG)
logger.addHandler(ConsoleOutputHandler)


# Install rich's traceback handler to automatically format tracebacks
rich_install()


async def main():
    file_path = [
        Path("data/YamEnterprises_Monotype Fonts Plan License.US.en 04.0 (BLP).pdf")
    ]
    file_path = [
        Path(
            "data/YamEnterprises_Monotype Fonts Plan License.US.en 04.0 (BLP) reduced.pdf"
        )
    ]

    config_file_name = (
        "/Users/jchevall/Coding/quivr/backend/core/tests/rag_config_workflow.yaml"
    )

    assistant_config = AssistantConfig.from_yaml(config_file_name)
    # megaparse_config = find_nested_key(config, "megaparse_config")
    megaparse_config = assistant_config.ingestion_config.parser_config.megaparse_config
    megaparse_config.llama_parse_api_key = os.getenv("LLAMA_PARSE_API_KEY")

    processor_kwargs = {
        "megaparse_config": megaparse_config,
        "splitter_config": assistant_config.ingestion_config.parser_config.splitter_config,
    }

    brain = await Brain.afrom_files(
        name="test_brain",
        file_paths=file_path,
        processor_kwargs=processor_kwargs,
    )

    # # Check brain info
    brain.print_info()

    questions = [
        "What is the contact name for Yam Enterprises?",
        "What is the customer phone for Yam Enterprises?",
        "What is the Production Fonts (maximum) for Yam Enterprises?",
        "List the past use font software according to past use term for Yam Enterprises.",
        "How many unique Font Name are there in the Add-On Font Software Section for Yam Enterprises?",
        "What is the maximum number of Production Fonts allowed based on the license usage per term for Yam Enterprises?",
        "What is the number of production fonts licensed by Yam Enterprises? List them one by one.",
        "What is the number of Licensed Monthly Page Views for Yam Enterprises?",
        "What is the monthly licensed impressions (Digital Marketing Communications) for Yam Enterprises?",
        "What is the number of Licensed Applications for Yam Enterprises?",
        "For Yam Enterprises what is the number of applications aggregate Registered users?",
        "What is the number of licensed servers for Yam Enterprises?",
        "When is swap of Production Fonts available in Yam Enterprises?",
        "Who is the primary licensed monotype fonts user for Yam Enterprises?",
        "What is the number of Licensed Commercial Electronic Documents for Yam Enterprises?",
        "How many licensed monotype fonts users can Yam Enterprises have?",
        "How many licensed desktop users can Yam Enterprises have?",
        "Which contract type does Yam Enterprises follow?",
        "What monotype fonts support does Yam Enterprises have?",
        "Which monotype font services onboarding does Yam Enterprises have?",
        "Which Font/User Management does Yam Enterprises have?",
        "What Add-on inventory set did Yam Enterprises pick?",
        "Does Yam Enterprises have Single sign on?",
        "Is there Brand and Licence protection for Yam Enterprises?",
        "Who is the Third Party Payor's contact in Yam Enterprises?",
        "Does Yam Enterprises contract have Company Desktop License?",
        "What is the Number of Swaps Allowed for Yam Enterprises?",
        "When is swap of Production Fonts available in Yam Enterprises?",
    ]

    answers = [
        "Haruko Yamamoto",
        "81 90-1234-5603",
        "300 Production Fonts",
        "Helvetica Regular",
        "7",
        "300 Production Fonts",
        "Yam Enterprises has licensed a total of 105 Production Fonts.",
        "35,000,000",
        "2,500,000",
        "60",
        "40",
        "2",
        "Once per quarter",
        "Haruko Yamamoto",
        "0",
        "100",
        "60",
        "License",
        "Premier",
        "Premier",
        "Premier",
        "Plus",
        "Yes",
        "Yes",
        """
        Name: Yami Enterprises

        Contact: Mei Mei

        Address: 20-22 Tsuki-Tsuki-dori, Tokyo, Japan

        Phone: +81 71-9336-54023

        E-mail: mei.mei@example.com
        """,
        "Yes",
        "One (1) swap per calendar quarter",
        "The swap of Production Fonts will be available one (1) time per calendar quarter by removing Font Software as a Production Font and choosing other Font Software on the Monotype Fonts Platform.",
    ]

    retrieval_config = assistant_config.retrieval_config
    for i, (question, truth) in enumerate(zip(questions, answers, strict=False)):
        chunk = brain.ask(question=question, retrieval_config=retrieval_config)
        # LINEAJE: enforce() `question` at agent->log log_emit — this payload crossed a trust boundary with no runtime policy check. Mask/block; do not remove without review. site_id='site:sha256:d475d1e22867bfee41f2be2f5cf1116e8eadef2ad2efc1ea7a3071a2208716ec'
        _gr_client = _lineaje_load_gr_client()
        _gr_site = _gr_client.SiteDescriptor(site_id='site:sha256:d475d1e22867bfee41f2be2f5cf1116e8eadef2ad2efc1ea7a3071a2208716ec', phase='log_emit', boundary={'source': 'log', 'sink': 'log'}, candidate_policies=[], fail_mode='ALLOW_WITH_AUDIT', source_type='agent', destination_type='log', project='lineaje-openclaw', organization='Root Organization', project_name='quivr', project_version='main', project_branch='main', components={'identity': {'app': {'name': 'quivr', 'version': 'main', 'purl': 'pkg:github/lineaje-demo/quivr@main?commit-id=cb72bb5e125b56bc68c0a6ef2b473794a944ef53&commit-time=2026-09-27%2000%3A34%3A20%20%2B0000&build_file=core/pyproject.toml&repo_strategy=single-repo'}}, 'invocation': {'file': 'examples/pdf_document_from_yaml.py', 'line': 135, 'function': 'main'}})
        try:
            question = await __import__('asyncio').to_thread(lambda: _gr_client.enforce(_gr_site, question, content_type='application/json'))
        except _gr_client.GuardrailUnavailableError:
            pass
        except PermissionError:
            pass
        print(
            "\n Question: ", question, "\n Answer: ", chunk.answer, "\n Truth: ", truth
        )
        if i == 5:
            break


if __name__ == "__main__":
    dotenv.load_dotenv()

    # Run the main function in the existing event loop
    asyncio.run(main())
