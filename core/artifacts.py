import os
import json
import ast
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from slack_bot.client import slack_service

logger = logging.getLogger("synapse.artifacts")

ARTIFACTS_DIR = Path("/home/ilyan/random/synapse/artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

class ArtifactGenerator:
    """
    Generates and persists production-ready .py scripts, .ipynb Jupyter notebooks,
    and documents from War Room agent outputs, and uploads them to Slack.
    """

    @staticmethod
    def validate_python_syntax(code: str) -> bool:
        """Validates that python code has no syntax errors using AST parser."""
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.warning(f"Python syntax error in generated code: {e}")
            return False

    @staticmethod
    def create_python_script(filename: str, code: str, header_doc: str = "") -> Path:
        """Saves clean Python code to a .py file."""
        if not filename.endswith(".py"):
            filename += ".py"
        filepath = ARTIFACTS_DIR / filename
        
        content = ""
        if header_doc:
            content += f'"""\n{header_doc.strip()}\n"""\n\n'
        content += code.strip() + "\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"Generated Python script artifact: {filepath}")
        return filepath

    @staticmethod
    def create_jupyter_notebook(filename: str, code_cells: List[str], markdown_cells: Optional[List[str]] = None) -> Path:
        """
        Builds a valid Jupyter Notebook (v4 format) with markdown and code cells.
        """
        if not filename.endswith(".ipynb"):
            filename += ".ipynb"
        filepath = ARTIFACTS_DIR / filename

        cells = []
        md_list = markdown_cells or []

        # Interleave markdown and code cells
        total = max(len(code_cells), len(md_list))
        for i in range(total):
            if i < len(md_list) and md_list[i]:
                cells.append({
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [line + "\n" for line in md_list[i].split("\n")]
                })
            if i < len(code_cells) and code_cells[i]:
                cells.append({
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [line + "\n" for line in code_cells[i].split("\n")]
                })

        notebook = {
            "cells": cells,
            "metadata": {
                "language_info": {"name": "python"},
                "orig_nbformat": 4
            },
            "nbformat": 4,
            "nbformat_minor": 2
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=2)

        logger.info(f"Generated Jupyter Notebook artifact: {filepath}")
        return filepath

    @staticmethod
    def upload_to_slack(
        filepath: Path,
        channel_id: str,
        thread_ts: Optional[str] = None,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None
    ) -> bool:
        """
        Uploads an artifact file to Slack channel/thread if files:write scope is available.
        """
        if not slack_service.client:
            return False

        try:
            res = slack_service.client.files_upload_v2(
                channel=channel_id,
                thread_ts=thread_ts,
                file=str(filepath),
                title=title or filepath.name,
                initial_comment=initial_comment or f"📁 *Artifact Generated:* `{filepath.name}`"
            )
            return res.get("ok", False)
        except Exception as e:
            logger.warning(f"Could not upload file to Slack (check files:write scope): {e}")
            # Fallback notification in thread
            slack_service.post_message(
                text=(
                    f"📁 *Artifact Created:* `{filepath.name}`\n"
                    f"💾 *Saved locally at:* `{filepath}`\n"
                    f"_(Enable `files:write` in Slack App OAuth to download files directly in Slack)_"
                ),
                channel=channel_id,
                thread_ts=thread_ts,
                username="Synapse Artifacts",
                icon_emoji=":floppy_disk:"
            )
            return False

artifact_generator = ArtifactGenerator()
