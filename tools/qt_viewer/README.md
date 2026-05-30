# Qt viewers for llove

> **日本語のかみ砕いた説明**
> これは llove の「目で見る」ための、おまけの道具です。
>
> llove を動かすと、できごとの記録が文字でずらっと残ります。その中には、カメラで写した絵と「ここがあやしい」と囲んだ印の記録や、空中にちらばった点で形を表した記録(横や上から見て位置がわかるもの)もあります。ただ、文字の画面のままでは絵として見づらいので、この道具は別の小さな窓を開いて、その絵をちゃんとした絵として大きく映してくれます。
>
> この道具は llove の本体の一部ではありません。llove 本体に最初から組み込むと、ふだん文字だけで十分な人にまで重たい部品を背負わせてしまうので、わざと外に出して「使いたい人だけ後から付け足す」形にしています。使うときは、絵を映すための部品をひとつだけ別に入れる必要があります(入れ方は下の手順にあります)。llove は「文字の画面ですぐ見られる・特別な絵の機能はいらない」を大事にしているので、その約束をこわさないために、この絵を映す道具だけ切り離してあります。
>
> → 用語集: [GLOSSARY.md](../../docs/GLOSSARY.md)

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
