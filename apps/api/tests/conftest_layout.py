"""Synthetic layout fixtures created in memory; no external corpus is downloaded."""

from collections.abc import Callable

import pymupdf
import pytest


@pytest.fixture
def layout_pdf() -> Callable[[str], bytes]:
    def build(kind: str) -> bytes:
        with pymupdf.open() as document:
            page = document.new_page(width=612, height=792)
            if kind == "columns":
                page.insert_text((50, 60), "Research findings", fontsize=18)
                # Draw the right column first: reading order must come from layout.
                right = (
                    "Right opening describes the evaluation.\n"
                    "The methods were tested on held-out research papers. "
                    "Each question was checked against its original evidence.\n\n"
                    "Right conclusion reports the final comparison."
                )
                left = (
                    "Left opening introduces the experiment.\n"
                    "Researchers collected several independent observations. "
                    "The evidence was reviewed and organized by source.\n\n"
                    "Left conclusion completes the first discussion."
                )
                assert (
                    page.insert_textbox(pymupdf.Rect(330, 100, 560, 650), right, fontsize=11) >= 0
                )
                assert page.insert_textbox(pymupdf.Rect(50, 100, 280, 650), left, fontsize=11) >= 0
            elif kind in {"table", "shaded_table"}:
                page.insert_text((50, 70), "Retrieval evaluation", fontsize=18)
                x_positions = [50, 220, 380, 550]
                y_positions = [140, 180, 220, 260]
                for x in x_positions:
                    page.draw_line((x, 140), (x, 260), width=1)
                for y in y_positions:
                    page.draw_line((50, y), (550, y), width=1)
                rows = [
                    ["Model", "Recall", "Latency"],
                    ["Baseline", "0.80", "800 ms"],
                    ["Hybrid", "0.86", "1100 ms"],
                ]
                for row_index, row in enumerate(rows):
                    for column_index, text in enumerate(row):
                        page.insert_text(
                            (x_positions[column_index] + 8, 165 + row_index * 40),
                            text,
                            fontsize=11,
                        )
                if kind == "shaded_table":
                    page.draw_rect(pymupdf.Rect(50, 330, 550, 390), fill=(0.94, 0.96, 0.98))
                    page.insert_text(
                        (60, 355), "Shaded evidence must remain beside the table.", fontsize=11
                    )
            elif kind == "shaded_code":
                page.draw_rect(pymupdf.Rect(50, 50, 560, 740), fill=(0.94, 0.96, 0.98))
                page.insert_text(
                    (60, 100),
                    "app/main.py\napp/core/config.py\nservices/ingestion/\ntests/test_ingestion.py",
                    fontname="cour",
                    fontsize=11,
                )
            elif kind == "multipage":
                page.insert_text(
                    (50, 100),
                    "First page evidence is kept here. Caf\u00e9.\n"
                    "Supporting details explain the result.",
                    fontsize=12,
                )
                document.new_page(width=612, height=792)  # Preserve an empty middle page.
                last = document.new_page(width=612, height=792)
                last.insert_text(
                    (50, 100),
                    "Third page evidence remains separate.\nSupporting details track the source.",
                    fontsize=12,
                )
            elif kind == "headers":
                for index in range(2):
                    if index:
                        page = document.new_page(width=612, height=792)
                    page.insert_text((50, 25), "Research journal running header", fontsize=9)
                    page.insert_text((50, 180), f"Body evidence on page {index + 1}.", fontsize=12)
                    page.insert_text((50, 770), "Journal footer retained for cleanup", fontsize=9)
            elif kind == "image":
                pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
                pixmap.clear_with(255)
                page.insert_image(pymupdf.Rect(50, 50, 550, 700), stream=pixmap.tobytes("png"))
            elif kind == "text":
                page.insert_text(
                    (50, 100),
                    "Evidence stays attached to its source page. Caf\u00e9.\n"
                    "Supporting details explain the result.",
                    fontsize=12,
                )
            else:
                raise ValueError("Unknown layout fixture")
            return document.tobytes()

    return build
