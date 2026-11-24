"""Reproduce descriptive statistics, not an astronomical classification."""

import argparse
import csv
import io
import json
import math


def analyze(datasets, parameters):
    if parameters["ztf_media_type"] == "application/json":
        data = json.loads(datasets["ztf"])
        rows = data
        for key in parameters["ztf_row_selector"]:
            rows = rows[key]
        object_data = data[parameters["ztf_row_selector"][0]]
        if object_data["meta"]["filter"] != parameters["band"]:
            raise ValueError("Photometric band differs from frozen source metadata")
    else:
        rows = list(csv.DictReader(io.StringIO(datasets["ztf"])))
    columns = parameters["columns"]
    selected = []
    for index in parameters["ztf_rows"]:
        row = rows[index]
        time, value, error = (float(row[columns[key]]) for key in ("time", "value", "uncertainty"))
        if not all(math.isfinite(number) for number in (time, value, error)) or error <= 0:
            raise ValueError("Nonfinite measurement or nonpositive uncertainty")
        if columns["band"] is not None and row[columns["band"]] != parameters["band"]:
            raise ValueError("Do not mix photometric bands")
        selected.append((time, value, error))
    if len(selected) < 3 or len({item[0] for item in selected}) < 3:
        raise ValueError("At least three distinct observation times are required")
    selected.sort()
    weights = [1 / error ** 2 for _, _, error in selected]
    mean = sum(point[1] * weight for point, weight in zip(selected, weights)) / sum(weights)
    chi_squared = sum(((point[1] - mean) / point[2]) ** 2 for point in selected)
    delta = selected[-1][1] - selected[0][1]
    delta_error = math.hypot(selected[0][2], selected[-1][2])
    return {"n": len(selected), "weighted_mean_mag": mean, "weighted_mean_error_mag": math.sqrt(1 / sum(weights)),
            "constant_model_chi_squared": chi_squared, "degrees_of_freedom": len(selected) - 1,
            "endpoint_delta_mag": delta, "endpoint_delta_error_mag": delta_error,
            "endpoint_delta_over_error": delta / delta_error,
            "caution": "Reported measurement errors only; systematic and correlated errors are not modeled. "
                       "Descriptive statistics do not establish an astronomical class or discovery."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as stream:
        data = json.load(stream)
    print(json.dumps(analyze(data["datasets"], data["parameters"]), allow_nan=False, sort_keys=True))
