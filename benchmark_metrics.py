"""
Замер РЕАЛЬНЫХ метрик (P / R / mAP@0.5 / mAP@0.5:0.95) на val + test split D-Fire.

Этот скрипт нужен, чтобы вставить настоящие цифры в презентацию (слайд 13).
Прогоняет model.val() с split='val' и split='test' для всех моделей.

Использование:
    python benchmark_metrics.py
"""

import csv
from pathlib import Path

import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent

MODELS = {
    "YOLOv8m":  ROOT / "best.pt",                                                # дообученный v8m best.pt (поменяй путь, если у тебя в другом месте)
    "YOLO26m":  ROOT / "runs_yolo26m" / "yolo26m_dfire_safe" / "weights" / "best.pt",
    "YOLO26s":  ROOT / "runs_yolo26s" / "yolo26m_dfire4"     / "weights" / "best.pt",
}

DATA_YAML = ROOT / "data" / "data.yaml"
DEVICE    = 0 if torch.cuda.is_available() else "cpu"
IMGSZ     = 640
BATCH     = 16
WORKERS   = 0    # 0 на Windows — обходим multiprocessing-quirks, заодно стабильнее


def evaluate(model, split, plots=False):
    """Одна проверка на нужном split."""
    return model.val(
        data    = str(DATA_YAML),
        imgsz   = IMGSZ,
        batch   = BATCH,
        device  = DEVICE,
        split   = split,
        workers = WORKERS,
        plots   = plots,
        verbose = True,
    )


def main():
    assert DATA_YAML.exists(), f"data.yaml не найден: {DATA_YAML}"
    print(f"Device: {DEVICE}")
    print(f"Data:   {DATA_YAML}\n")

    rows = []
    for name, path in MODELS.items():
        if not Path(path).exists():
            print(f"[!] Пропуск {name}: {path} не найден")
            continue
        print(f"\n{'='*72}\n  {name}\n{'='*72}")

        model = YOLO(str(path))

        for split, plots in (("val", False), ("test", True)):
            print(f"\n  Прогон model.val() на split='{split}'")
            m = evaluate(model, split, plots=plots)

            print(f"\n  --- {split.upper()} split ---")
            print(f"  all  P={m.box.mp:.3f}  R={m.box.mr:.3f}"
                  f"  mAP50={m.box.map50:.3f}  mAP50-95={m.box.map:.3f}")

            # По классам
            names = m.names
            per_class = {}
            for i, cls_name in names.items():
                per_class[cls_name] = {
                    "P":         float(m.box.p[i]),
                    "R":         float(m.box.r[i]),
                    "mAP50":     float(m.box.ap50[i]),
                    "mAP50-95":  float(m.box.ap[i]),
                }
                print(f"  {cls_name:<6} P={per_class[cls_name]['P']:.3f}"
                      f"  R={per_class[cls_name]['R']:.3f}"
                      f"  mAP50={per_class[cls_name]['mAP50']:.3f}"
                      f"  mAP50-95={per_class[cls_name]['mAP50-95']:.3f}")

            rows.append({
                "model":    name,
                "split":    split,
                "class":    "all",
                "P":        round(m.box.mp, 4),
                "R":        round(m.box.mr, 4),
                "mAP50":    round(m.box.map50, 4),
                "mAP50-95": round(m.box.map, 4),
            })
            for cn, pm in per_class.items():
                rows.append({
                    "model":    name,
                    "split":    split,
                    "class":    cn,
                    "P":        round(pm["P"], 4),
                    "R":        round(pm["R"], 4),
                    "mAP50":    round(pm["mAP50"], 4),
                    "mAP50-95": round(pm["mAP50-95"], 4),
                })

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # CSV
    out = ROOT / "metrics_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["model", "split", "class", "P", "R", "mAP50", "mAP50-95"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV сохранён: {out}")


if __name__ == "__main__":
    # На Windows multiprocessing требует этот guard.
    main()
