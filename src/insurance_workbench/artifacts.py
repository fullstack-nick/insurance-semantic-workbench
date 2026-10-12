"""Content-addressed semantic inputs retained with each published projection."""

from .config import ROOT, settings
from .util import digest


def freeze(manifest):
    identity = digest(manifest)
    directory = settings().data_root / "releases" / identity
    for name, checksum in manifest["files"].items():
        source = ROOT / "semantic" / name
        target = directory / name
        content = source.read_bytes()
        if digest(content) != checksum:
            raise ValueError("Semantic input changed while freezing the release")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
        if digest(target.read_bytes()) != checksum:
            raise ValueError("Archived semantic input hash mismatch")
    return directory


def resolve(manifest):
    directory = settings().data_root / "releases" / digest(manifest)
    for name, checksum in manifest["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or digest(path.read_bytes()) != checksum:
            raise ValueError("Pinned semantic artifact is missing or corrupt")
    return directory


def for_snapshot(snapshot):
    manifest = snapshot["manifest"].get("semantic_inputs")
    # Early development probes predate archival. Their saved evidence remains immutable,
    # but the verification reports deliberately use only projections with frozen inputs.
    return resolve(manifest) if manifest else ROOT / "semantic"
