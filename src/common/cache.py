"""Parquet read/write with provenance sidecars.

Every dataset written to data/interim or data/final gets a JSON sidecar
(<name>.provenance.json) recording where it came from, when it was built,
and by which parser version, so any table in the repo is traceable back to
raw responses without re-reading code.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class Provenance:
    source_urls: list[str] = field(default_factory=list)
    scrape_timestamp: str | None = None
    parser: str = ""
    parser_version: str = "0.1.0"
    row_count: int | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "source_urls": self.source_urls,
            "scrape_timestamp": self.scrape_timestamp,
            "parser": self.parser,
            "parser_version": self.parser_version,
            "row_count": self.row_count,
            "notes": self.notes,
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


def write_parquet(df: pd.DataFrame, path: Path, provenance: Provenance) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    provenance.row_count = len(df)
    df.to_parquet(path, index=False)
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    sidecar.write_text(json.dumps(provenance.to_dict(), indent=2))
    return path


def read_parquet(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. This project runs analysis/viz stages entirely from cache; "
            f"run the corresponding scrape/parse stage first."
        )
    return pd.read_parquet(path)


def read_provenance(path: Path) -> dict:
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    if not sidecar.exists():
        raise FileNotFoundError(f"no provenance sidecar for {path}")
    return json.loads(sidecar.read_text())


def exists(path: Path) -> bool:
    return Path(path).exists()


def main():
    import numpy as np
    demo = pd.DataFrame({"a": [1, 2, 3], "b": np.random.rand(3)})
    out = write_parquet(demo, Path("/tmp/clo_atlas_cache_demo.parquet"),
                         Provenance(source_urls=["https://example.com"], parser="demo", scrape_timestamp="now"))
    print(read_parquet(out))
    print(read_provenance(out))


if __name__ == "__main__":
    main()
