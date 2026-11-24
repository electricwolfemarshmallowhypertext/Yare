"""Download a bounded public ZTF/Gaia example; never use credentials."""

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


SOURCES = (
    ("ztf", "https://db.ztf.snad.space/api/v3/data/dr24/oid/full/json", "ZTF DR24 via SNAD",
     {"oid": "686103400034440"}),
    ("gaia", "https://gea.esac.esa.int/tap-server/tap/sync", "Gaia DR3",
     {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY":
      "SELECT TOP 5 source_id,ra,dec,ref_epoch,ra_error,dec_error,parallax,parallax_error,phot_g_mean_mag "
      "FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),"
      "CIRCLE('ICRS',298.0025,29.87147,0.0014)) ORDER BY source_id"}),
)


def freeze(output):
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.json"
    if manifest.exists():
        raise ValueError("Frozen manifest exists; choose a new directory instead of overwriting it")
    datasets, pending = [], []
    for name, url, release, query in SOURCES:
        path = output / (name + (".json" if name == "ztf" else ".csv"))
        if path.exists():
            raise ValueError("Dataset already exists; choose a new directory")
        with requests.get(url, params=query, timeout=(15, 60), stream=True) as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_content(16384):
                raw.extend(chunk)
                if len(raw) > 262144:
                    raise ValueError("Public response exceeded the example byte bound")
        text = bytes(raw).decode("utf-8")
        rows = json.loads(text)[query["oid"]]["lc"] if name == "ztf" else list(csv.DictReader(io.StringIO(text)))
        expected = {"mag", "magerr", "mjd"} if name == "ztf" else {"source_id", "ra", "dec"}
        if not rows or not expected <= set(rows[0]):
            raise ValueError("Public response lacks required nonempty observations: " + name)
        pending.append((path, bytes(raw)))
        dataset = {"id": name, "path": path.name, "source_url": url, "query": query,
                         "release": release, "acquired_at": datetime.now(timezone.utc).isoformat(),
                         "media_type": "application/json" if name == "ztf" else "text/csv",
                         "sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows)}
        if name == "ztf":
            dataset["row_selector"] = [query["oid"], "lc"]
        datasets.append(dataset)
    for path, raw in pending:
        path.write_bytes(raw)
    for dataset in datasets:
        print(dataset["id"] + ": frozen " + str(dataset["rows"]) + " public rows")
    manifest.write_text(json.dumps({"version": "public-astronomy-data.v1", "datasets": datasets},
                                   indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(freeze(parser.parse_args().output))
