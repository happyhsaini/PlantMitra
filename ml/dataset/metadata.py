"""In-memory access to official Pl@ntNet-300K-v2 CSV metadata."""

from __future__ import annotations

import csv
import io
import urllib.request
from dataclasses import dataclass
from typing import Iterable

ZENODO_FILES = "https://zenodo.org/records/10419064/files/"
SPECIES_METADATA_URL = ZENODO_FILES + "species_metadata.csv?download=1"
IMAGE_METADATA_URL = ZENODO_FILES + "plantnet300K_metadata.csv?download=1"


def _read_csv(url: str, timeout: float = 90) -> list[dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "PlantMitra-remote-dataset/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return list(csv.DictReader(io.TextIOWrapper(response, encoding="utf-8-sig", newline="")))


@dataclass(frozen=True)
class PlantImageRecord:
    species_id: str
    scientific_name: str
    full_species: str
    family: str
    organ: str
    author: str
    license: str
    split: str
    pn_hash: str
    observation_id: str

    @property
    def zip_path(self) -> str:
        return f"images/{self.split}/{int(self.species_id):04d}/{self.pn_hash}.jpg"


def load_records(
    scientific_names: Iterable[str] | None = None,
    allowed_licenses: Iterable[str] = ("cc-by-sa",),
    species_metadata_url: str = SPECIES_METADATA_URL,
    image_metadata_url: str = IMAGE_METADATA_URL,
) -> tuple[dict[str, dict[str, str]], list[PlantImageRecord]]:
    """Load metadata in memory and join image rows to the official species mapping."""
    species_rows = _read_csv(species_metadata_url)
    image_rows = _read_csv(image_metadata_url)
    species_by_id = {row["species_id"]: row for row in species_rows}
    wanted = set(scientific_names) if scientific_names is not None else None
    licenses = {value.strip().lower() for value in allowed_licenses}
    records: list[PlantImageRecord] = []

    for row in image_rows:
        species = species_by_id.get(row["species_id"])
        if not species:
            continue
        name = species["species"].strip()
        if wanted is not None and name not in wanted:
            continue
        license_name = row["license"].strip().lower()
        if license_name not in licenses:
            continue
        records.append(PlantImageRecord(
            species_id=row["species_id"], scientific_name=name,
            full_species=species["full_species"].strip(), family=species["family"].strip(),
            organ=row["organ"].strip(), author=row["author"].strip(), license=license_name,
            split=row["split"].strip(), pn_hash=row["PN_hash"].strip(),
            observation_id=row["PN_observation_id"].strip(),
        ))
    return species_by_id, records
