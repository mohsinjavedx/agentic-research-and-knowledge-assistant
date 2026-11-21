from uuid import UUID

import pytest

from app.services.generation.evidence import focus_evidence
from app.services.retrieval.dense import RetrievedChunk


def source(text: str, index: int = 0) -> RetrievedChunk:
    return RetrievedChunk(UUID(int=index + 1), UUID(int=100), index + 1, index, text, 0.8)


def test_focus_selects_complete_answer_paragraph_and_preserves_source_range() -> None:
    background = "Background on educational question answering. " * 40
    facts = "Five benchmarks are AI2_ARC, OpenBookQA, E-EVAL, TQA, and ScienceQA."
    original = background + "\n\n## Evaluation datasets\n\n" + facts
    passages = focus_evidence("Which five benchmarks evaluate the system?", [source(original)])
    assert len(passages) == 1
    passage = passages[0]
    assert facts in passage.text
    assert background not in passage.text
    assert original[passage.start : passage.end] == passage.text
    assert "Evaluation datasets" in passage.text
    assert passage.retrieval_index == 0


def test_focus_keeps_a_complete_list_with_its_introductory_qualifier() -> None:
    text = (
        "Only for the test cohort, the benchmarks were:\n"
        "- Alpha\n- Beta\n- Gamma\n\nUnrelated context."
    )
    passage = focus_evidence("Which benchmarks were used?", [source(text)])[0]
    assert "Only for the test cohort" in passage.text
    assert "- Alpha\n- Beta\n- Gamma" in passage.text


@pytest.mark.parametrize(
    "question", ["Which benchmarks were used?", "Which benchmarks include Beta?"]
)
def test_blank_lines_do_not_separate_a_list_from_its_intro_or_drop_later_items(
    question: str,
) -> None:
    text = (
        "Only for the test cohort, the benchmarks were:\n\n"
        "- Alpha\n\n- Beta\n\n- Gamma\n\nUnrelated discussion."
    )
    passage = focus_evidence(question, [source(text)])[0]
    assert passage.text == text[: text.index("\n\nUnrelated")]


def test_focus_never_cuts_a_table_or_its_header_to_meet_an_arbitrary_size() -> None:
    table = "| Model | Accuracy |\n| --- | --- |\n" + "| Baseline | 85.5 |\n" * 100
    text = "## Table 4\n\n" + table + "\nOther findings."
    passage = focus_evidence("What accuracy does Baseline report in Table 4?", [source(text)])[0]
    assert table.rstrip() in passage.text
    assert "Model | Accuracy" in passage.text


def test_focus_keeps_unicode_offsets_and_original_retrieval_indices() -> None:
    text = "Café background.\n\n## Results\n\nThe naïve system scored 91%."
    passages = focus_evidence(
        "What did the system score?", [source("Other source."), source(text, 1)]
    )
    selected = passages[1]
    assert selected.retrieval_index == 1
    assert text[selected.start : selected.end] == selected.text
    assert "naïve" in selected.text
