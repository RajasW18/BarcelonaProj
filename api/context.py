"""Attachment and public URL context extraction for chat requests."""
import base64
import json
import mimetypes
from html.parser import HTMLParser
from pathlib import Path

import httpx
from fastapi import UploadFile
from openai import AsyncOpenAI

from api.config import settings

MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".py", ".ts", ".tsx",
    ".js", ".jsx", ".html", ".css", ".sql", ".yaml", ".yml",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def _html_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "\n".join(parser.parts)


async def _extract_file(file: UploadFile) -> tuple[str, str]:
    name = Path(file.filename or "attachment").name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"{name}: this file type is not supported.")

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{name}: files must be 25 MB or smaller.")

    if suffix == ".pdf":
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix == ".docx":
        from docx import Document
        import io
        document = Document(io.BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    elif suffix in {".json"}:
        text = json.dumps(json.loads(data.decode("utf-8")), indent=2)
    else:
        text = data.decode("utf-8", errors="replace")

    return name, text[:120_000]


async def _describe_image(name: str, data: bytes, content_type: str) -> str:
    if settings.groq_api_key:
        client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=120,
        )
        model = settings.groq_vision_model
    else:
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=120,
        )
        model = settings.ollama_vision_model

    encoded = base64.b64encode(data).decode("ascii")
    filename_hint = Path(name).stem.replace("_", " ").replace("-", " ").strip()
    response = await client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Analyze this football image for a chat assistant. First describe "
                        "visible evidence such as the player, kit, badge, shirt number, "
                        "competition, and any readable text. Then assess likely identity "
                        "only when the evidence supports it. The uploaded filename is "
                        f"'{name}' and may be a user-provided clue, not proof. Its readable "
                        f"name is '{filename_hint}'. If the filename suggests a known "
                        "player, explain that it is a filename hint and cross-check it "
                        "against the visible football details. Never infer identity from "
                        "age, ethnicity, hair, or facial appearance alone. State uncertainty."
                    ),
                },
                {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded}"}},
            ],
        }],
        max_tokens=1200,
    )
    description = response.choices[0].message.content or "No image description returned."
    return (
        f"[Image: {name}]\n"
        f"Filename hint: {filename_hint}\n"
        f"{description}"
    )


async def prepare_context(files: list[UploadFile], url: str | None) -> dict:
    sections: list[str] = []
    sources: list[str] = []

    for file in files:
        name = Path(file.filename or "attachment").name
        content_type = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
        data = await file.read()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"{name}: files must be 25 MB or smaller.")
        await file.seek(0)
        if content_type.startswith("image/"):
            sections.append(await _describe_image(name, data, content_type))
        else:
            extracted_name, text = await _extract_file(file)
            sections.append(f"[File: {extracted_name}]\n{text}")
        sources.append(name)

    if url:
        parsed = httpx.URL(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only public HTTP and HTTPS URLs are supported.")
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            response = await client.get(str(parsed), headers={"User-Agent": "BarcaBot/1.0"})
            response.raise_for_status()
        text = _html_text(response.text)[:120_000]
        sections.append(f"[Website: {url}]\n{text}")
        sources.append(url)

    return {"context": "\n\n---\n\n".join(sections), "sources": sources}
