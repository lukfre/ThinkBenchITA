"""Benchmark loaders. Each module registers one or more `build() -> Built`.

A loader downloads the source at a pinned revision, converts it to the unified
format (schema.Item) and reports what it found. It does no network access
beyond the Hub / GitHub download and never edits source text.
"""

import urllib.request
from pathlib import Path
from typing import Callable

from ..schema import ROOT, Built

# Revisions inspected on 2026-10-06. Loaders download exactly these.
REVISIONS = {
    "Qwen/PolyMath": "71e0db902e0ece05e208dfd8b1695bd3d95cf130",
    "amphora/MCLM": "aa789e49b04d5ca054c3a2a70d9bacd8a7499106",
    "HuggingFaceH4/MATH-500": "6e4ed1a2a79af7d8630a6b768ec859cb5af4d3be",
    "Idavidrein/gpqa": "83022cefff930aea54f654c0b282e74b9eeda5c6",
    "ellamind/gpqa-multilingual": "bc70ca1791afa241a98c972e126c2decaf0a367d",
    "allenai/ZebraLogicBench-private": "9f39ef490ae924437376657205025f26c0bd1af3",
    "evalplus/humanevalplus": "d32357cf319e50e9c8d8dab5ea876c72b0fd321b",
    "evalplus/mbppplus": "b2d74c91837c3f2a20c1299ae98133cbe7cfa077",
    "openai/openai_humaneval": "7dce6050a7d6d172f3cc5c32aa97f52fa1a2e544",
    "facebook/Multi-IF": "0ab97ce0b45c7f57772e8ba2ac1616f4b00bd3aa",
    "zhihz0535/X-AlpacaEval": "4dc0165d07b6dbf2d6c011a35ade071ac5ae0dc4",
    "livecodebench/code_generation_lite": "0fe84c3912ea0c4d4a78037083943e8f0c4dd505",
    "MathArena/aime_2025": "c94da77eb22bbd6439e62a323bec18493a421302",
    "fedric95/AIME2025-Multilingual": "ae0d215bc4dd76b4e8ee59f1e80f962a9893e970",
    "ai4text/Invalsi": "9656a495f96a6d90dd640c6f2b5536ceb93343ac",
}

LOADERS: dict[str, Callable[[], Built]] = {}


def register(name: str):
    def deco(fn):
        LOADERS[name] = fn
        return fn

    return deco


class SourceUnavailable(RuntimeError):
    """The source cannot be downloaded with the current credentials (gated repo)."""


def hf_file(repo: str, filename: str) -> Path:
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import GatedRepoError

    try:
        return Path(hf_hub_download(repo, filename, repo_type="dataset", revision=REVISIONS[repo]))
    except GatedRepoError as e:
        raise SourceUnavailable(
            f"{repo} is gated and this Hugging Face account has not been granted access. "
            f"Accept the terms at https://huggingface.co/datasets/{repo} and rerun."
        ) from e


def subset(full: Built, keep, name: str, note: str) -> Built:
    """A benchmark made of some items of another: the same rows, issues and provenance."""
    items = {lang: [i for i in lang_items if keep(i)] for lang, lang_items in full.items.items()}
    return Built(items, full.issues, {**full.info, "name": name, "notes": [note, *full.info["notes"]]})


def source(repo: str) -> str:
    return f"{repo}@{REVISIONS[repo][:8]}"


def github_file(repo: str, commit: str, path: str) -> Path:
    """Download one file of a GitHub repo at a commit, cached under .cache/."""
    dest = ROOT / ".cache" / "github" / repo.replace("/", "__") / commit[:8] / path
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.request.quote(path)}"
        urllib.request.urlretrieve(url, dest)
    return dest


def release_file(url: str, sha256: str) -> Path:
    """Download a release asset once, cached under .cache/, and check its checksum."""
    import hashlib

    dest = ROOT / ".cache" / "releases" / sha256[:12] / url.rsplit("/", 1)[-1]
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != sha256:
        raise RuntimeError(f"{url}: checksum {digest} differs from the pinned {sha256}")
    return dest


from . import aime25, aiw, code_en, gpqa, invalsi, mclm, mhumaneval, multi_if, polymath, xalpaca, zebra  # noqa: E402,F401
