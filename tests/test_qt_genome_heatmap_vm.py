"""Stage 3 — genome heatmap view-model tests (pure, no Qt).

Builds an individuals x genes matrix from a snapshot's Genome3D ``c_factors``
(``factor_names`` [N] + ``factor_weights`` [N x K]) for the P5 heatmap. Tolerant:
individuals lacking a usable c_factors block, or with a different width than the
first, are skipped so the matrix stays rectangular.
"""

from __future__ import annotations

from llove.core.viewmodels.genome_heatmap import GenomeHeatmapVM

_SNAP = {
    "individuals": [
        {
            "individual_id": "a",
            "genome": {
                "c_factors": {
                    "factor_names": ["f0", "f1"],
                    "factor_weights": [[0.1, 0.2], [0.3, 0.4]],
                }
            },
        },
        {
            "individual_id": "b",
            "genome": {
                "c_factors": {
                    "factor_names": ["f0", "f1"],
                    "factor_weights": [[0.5, 0.6], [0.7, 0.8]],
                }
            },
        },
    ]
}


def test_builds_matrix_and_labels() -> None:
    h = GenomeHeatmapVM().load_snapshot(_SNAP)
    assert h.row_labels == ["a", "b"]
    assert h.col_labels == ["f0#0", "f0#1", "f1#0", "f1#1"]
    assert h.matrix == [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]


def test_empty_snapshot_yields_empty_matrix() -> None:
    h = GenomeHeatmapVM().load_snapshot({"individuals": []})
    assert h.matrix == []
    assert h.row_labels == []


def test_skips_individuals_without_factor_weights() -> None:
    snap = {
        "individuals": [
            _SNAP["individuals"][0],
            {"individual_id": "bad", "genome": {}},  # no c_factors -> skipped
            _SNAP["individuals"][1],
        ]
    }
    h = GenomeHeatmapVM().load_snapshot(snap)
    assert h.row_labels == ["a", "b"]
    assert len(h.matrix) == 2


def test_skips_width_mismatch_rows() -> None:
    snap = {
        "individuals": [
            _SNAP["individuals"][0],  # width 4
            {
                "individual_id": "wide",
                "genome": {
                    "c_factors": {
                        "factor_names": ["f0"],
                        "factor_weights": [[0.1, 0.2, 0.3]],  # width 3 -> skipped
                    }
                },
            },
        ]
    }
    h = GenomeHeatmapVM().load_snapshot(snap)
    assert h.row_labels == ["a"]


def test_tolerant_to_garbage() -> None:
    h = GenomeHeatmapVM().load_snapshot({})
    assert h.matrix == []
