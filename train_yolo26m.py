"""
Training script for Ultralytics YOLO26m on the D-Fire dataset.

YOLO26 was released on January 14, 2026 by Ultralytics. Compared to YOLOv8m
it brings:
  - DFL removal + end-to-end NMS-free head
  - ProgLoss + STAL loss (notably better on small objects -> smoke)
  - MuSGD optimizer (SGD + Muon hybrid) -> more stable convergence
  - yolo26m: ~20.4M params / 68.2 GFLOPs vs yolov8m: ~25.8M / 78.7 GFLOPs
    (smaller AND stronger on COCO: 53.1 mAP50-95 vs ~50.2)

Baseline to beat (YOLOv8m on D-Fire, reported by user):
    all   P=0.756  R=0.701  mAP50=0.768  mAP50-95=0.452
    fire  P=0.809  R=0.772  mAP50=0.832  mAP50-95=0.523
    smoke P=0.702  R=0.631  mAP50=0.705  mAP50-95=0.380

Requirements:
    pip install -U ultralytics    # must be >= 8.4.0 to ship YOLO26 weights
    A CUDA-capable GPU + matching torch build.
"""

import os
import torch
from ultralytics import YOLO


# ---------------------------------------------------------------------------
# Paths / device
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_YAML    = os.path.join(PROJECT_ROOT, "data", "data.yaml")
RUNS_DIR     = os.path.join(PROJECT_ROOT, "runs")

assert torch.cuda.is_available(), (
    "CUDA is not available. Install a CUDA build of torch and check that "
    "`nvidia-smi` works before launching training."
)
DEVICE = 0
print(f"Using device: cuda:{DEVICE}  ({torch.cuda.get_device_name(0)})")
print(f"Dataset config: {DATA_YAML}")


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def main():
    # Pretrained COCO weights are auto-downloaded on first use.
    model = YOLO("yolo26s.pt")

    results = model.train(
        data        = DATA_YAML,
        epochs      = 100,
        imgsz       = 640,
        batch       = 16,           # lower to 8 if you OOM on a 12 GB card
        device      = DEVICE,
        workers     = 8,
        optimizer   = "auto",       # picks MuSGD for YOLO26 automatically
        lr0         = 0.01,
        lrf         = 0.01,
        momentum    = 0.937,
        weight_decay= 0.0005,
        warmup_epochs = 3,
        cos_lr      = True,
        patience    = 30,           # early-stop if no improvement
        amp         = True,         # mixed precision on CUDA
        cache       = False,        # set True if your RAM fits the dataset
        project     = RUNS_DIR,
        name        = "yolo26m_dfire",
        exist_ok    = False,
        seed        = 42,
        verbose     = True,
        plots       = True,
        save        = True,
        save_period = 10,
        # end2end=True is the default for YOLO26 (NMS-free one-to-one head).
    )

    # -----------------------------------------------------------------------
    # Final validation on the val split with the best checkpoint
    # -----------------------------------------------------------------------
    best_pt = os.path.join(
        results.save_dir if hasattr(results, "save_dir") else
        os.path.join(RUNS_DIR, "yolo26m_dfire"),
        "weights", "best.pt",
    )
    print(f"\nBest weights: {best_pt}")

    best = YOLO(best_pt)
    metrics = best.val(
        data   = DATA_YAML,
        imgsz  = 640,
        batch  = 16,
        device = DEVICE,
        split  = "val",
        plots  = True,
        verbose= True,
    )
    print("\n=== Final val metrics ===")
    print(f"mAP50    : {metrics.box.map50:.4f}")
    print(f"mAP50-95 : {metrics.box.map:.4f}")
    print(f"Precision: {metrics.box.mp:.4f}")
    print(f"Recall   : {metrics.box.mr:.4f}")


if __name__ == "__main__":
    main()