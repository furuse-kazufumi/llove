# Qt viewers for llove

Standalone Qt-based viewers that render llove `vision` and `pointcloud`
scenario events richly — pixels, bounding boxes, rotatable 3D point clouds.

These tools are **not** a llove dependency. Install Qt locally:

```bash
pip install PySide6
```

(PyQt6 also works — both ship the same `QtWidgets` API. PySide6 is preferred
because it is permissively licensed.)

## Usage

```bash
# 1) Capture a llove scenario to a JSONL file
llove demo --scenario vision     | tee out/vision.jsonl
llove demo --scenario pointcloud | tee out/pointcloud.jsonl

# 2) Open the matching Qt viewer
python tools/qt_viewer/vision_viewer.py out/vision.jsonl
python tools/qt_viewer/pointcloud_viewer.py out/pointcloud.jsonl
```

(or for the same data shape, write a small JSONL by hand — each line is one
`Event` json — and feed it in.)

## Why standalone

llove's contract is "30 second terminal Artifact, no graphics required".
Adding Qt as an extras would push hundreds of MB of system libraries onto
users who only want the TUI. The viewers live in `tools/` so they are
opt-in, easy to ignore, and easy to swap (a Tk/Streamlit/HTML viewer for
the same JSONL would be a peer, not a replacement).

## Event schema consumed

Both viewers ignore unknown event kinds gracefully.

### vision_viewer.py reads

```jsonc
{
  "kind": "sensor",
  "payload": {
    "sensor_id": "defect_score",
    "value": 0.83,
    "frame_id": 4,
    "image_ascii": "...",
    "image_b64": null,            // optional — populated by richer pipelines
    "vlm_caption": "..."
  }
}
{
  "kind": "spc_alarm",
  "payload": {
    "frame_id": 4,
    "bbox": [13, 1, 16, 2],       // x1, y1, x2, y2 in the ASCII grid
    "value": 0.83,
    "threshold": 0.5
  }
}
```

When `image_b64` is missing (default in offline scenario), the viewer
upscales `image_ascii` to a black-and-white pixel image so a frame is
always visible. Bounding boxes are drawn from the SPC_ALARM payload.

### pointcloud_viewer.py reads

```jsonc
{
  "kind": "sensor",
  "payload": {
    "sensor_id": "tray_density",
    "value": 288,
    "frame_id": 1,
    "topview_ascii": "...",
    "points_xyz": [[x, y, z], ...],   // raw cloud
    "missing_slot": null                // or [col, row]
  }
}
```

Renders a top-down 2D scatter plot using QtGraphs / QChart, plus a
text panel with the missing-slot summary. Frame slider scrubs through
the captured stream.
