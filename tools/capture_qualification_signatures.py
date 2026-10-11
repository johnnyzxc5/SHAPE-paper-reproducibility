"""Maintainer utility: record numerical fingerprints of existing qualified HDF5.

This reads existing evidence only; it never generates trajectories or simulations.
The fingerprints permit future checks without distributing trajectory tensors.
"""
import argparse
import hashlib
import json
from pathlib import Path

UIDS = ("8167b058-dc6e-3b0a-b6b0-0478265cd56a", "216a0075-20d7-34a6-aded-c2198b018f7d")


def capture(source: Path) -> dict:
    import h5py
    from reproduce import sha
    receipt = source / "q2_controlled_physical_receipt.json"
    record = json.loads(receipt.read_text(encoding="utf-8"))
    if (record["physical_runs_completed"] != 96 or record["scientific_validator_passes"] != 96
            or record["failures"] != 0):
        raise ValueError("Source qualification did not validate all 96 runs")
    cases = []
    for uid in UIDS:
        path = source / "outputs/parent_9001_9100" / f"run_{uid}.h5"
        items = []
        with h5py.File(path, "r") as handle:
            if handle.attrs["observer_ctdq_backend"] != "finite_difference_batch_mex":
                raise ValueError("Source is not the qualified MEX backend")
            if int(handle.attrs["observer_ctdq_fallback_used"]) != 0:
                raise ValueError("Source used a backend fallback")

            def collect(name, dataset):
                if not isinstance(dataset, h5py.Dataset):
                    return
                value = dataset[()]
                names = {"float32": "single", "uint8": "uint8"}
                matlab_class = names[str(value.dtype)]
                # MATLAB HDF5 axes reverse h5py axes. The C-order little-endian
                # payload is consequently the MATLAB column-major payload.
                dimensions = list(reversed(value.shape))
                header = f"NUM|{matlab_class}|" + "".join(f"{n}x" for n in dimensions) + "|"
                digest = hashlib.sha256(header.encode("utf-8") +
                    value.astype(value.dtype.newbyteorder("<"), copy=False).tobytes(order="C")).hexdigest()
                items.append(dict(path="/" + name, matlab_class=matlab_class,
                                  matlab_size=dimensions, sha256=digest))
            handle.visititems(collect)
        if len(items) != 25:
            raise ValueError(f"Expected 25 datasets: {path}")
        cases.append(dict(run_uid=uid, source_hdf5_sha256=sha(path), datasets=items))
    return dict(schema_version="shape-qualified-pilot-numerical-signatures-v1",
                source_receipt=receipt.name, source_receipt_sha256=sha(receipt),
                source_scope="Existing 96-run Q2, 96 canonical validations, zero failures",
                encoding="shape.sha256_canonical(NUM); MATLAB dimensions; little-endian column-major",
                qualification_scope="Two contrasting Pilot LoE runs, all 25 datasets; serial reproduction only",
                cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
