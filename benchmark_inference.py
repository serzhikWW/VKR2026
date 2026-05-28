import os
import csv
import time
import statistics
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent

MODELS = {
    "YOLOv8m":  ROOT / "best.pt",
    "YOLO26m":  ROOT / "runs_yolo26m" / "yolo26m_dfire_safe" / "weights" / "best.pt",
    "YOLO26s":  ROOT / "runs_yolo26s" / "yolo26m_dfire4"     / "weights" / "best.pt",
}

VIDEOS = [
    ROOT / "videos" / "VP16.mp4",
    ROOT / "videos" / "Video shows intense flames, heavy smoke from Miami abandoned building fire.mp4",
]

IMGSZ        = 640
DEVICE       = 0  if torch.cuda.is_available() else "cpu"
WARMUP       = 30
N_INFER      = 200
MAX_FRAMES   = 500

assert torch.cuda.is_available(), "Нужна CUDA. Без GPU замер бесмысленен."
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"CUDA: {torch.version.cuda}, torch: {torch.__version__}\n")

def percentile(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def cuda_time_ms():
    torch.cuda.synchronize()
    return time.perf_counter() * 1000.0


def fmt_ms(x):
    return f"{x:.2f} ms"


def fmt_fps(x):
    return f"{x:.1f} FPS"



def bench_pure_inference(model, n_warmup=WARMUP, n_iter=N_INFER):
    """Чистый forward модели на синтетическом тензоре."""
    img = np.random.randint(0, 255, (IMGSZ, IMGSZ, 3), dtype=np.uint8)

    # warmup
    for _ in range(n_warmup):
        model.predict(img, imgsz=IMGSZ, device=DEVICE, verbose=False)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()

    times = []
    for _ in range(n_iter):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        model.predict(img, imgsz=IMGSZ, device=DEVICE, verbose=False)
        torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000.0)

    return {
        "mean_ms":   statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms":    percentile(times, 95),
        "p99_ms":    percentile(times, 99),
        "min_ms":    min(times),
        "max_ms":    max(times),
        "fps":       1000.0 / statistics.median(times),
        "vram_peak_mb": torch.cuda.max_memory_allocated() / 1024 / 1024,
    }


def bench_video_pipeline(model, video_path, max_frames=MAX_FRAMES):
    """Полный пайплайн: декод видео + инференс + постпроцессинг."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Не открывается: {video_path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    times = []
    frames_done = 0
    t_start = time.perf_counter()

    while frames_done < max_frames:
        ok, frame = cap.read()
        if not ok:
            break

        torch.cuda.synchronize()
        t0 = time.perf_counter()

        results = model.predict(frame, imgsz=IMGSZ, device=DEVICE, verbose=False)
        _ = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes is not None else []
        torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000.0)
        frames_done += 1

    cap.release()
    wall = time.perf_counter() - t_start

    return {
        "frames":      frames_done,
        "total_in_vid":total,
        "src_fps":     fps_src,
        "resolution":  f"{w}x{h}",
        "wall_sec":    wall,
        "wall_fps":    frames_done / wall if wall > 0 else 0,
        "median_ms":   statistics.median(times),
        "p95_ms":      percentile(times, 95),
        "mean_ms":     statistics.mean(times),
        "fps":         1000.0 / statistics.median(times),
    }



def main():
    out_rows = []

    for model_name, model_path in MODELS.items():
        if not Path(model_path).exists():
            print(f"[!] Пропуск {model_name}: файл не найден {model_path}")
            continue

        print(f"\n{'='*72}")
        print(f"  {model_name}  ({model_path.name})")
        print(f"{'='*72}")

        size_mb = model_path.stat().st_size / 1024 / 1024
        print(f"  Файл: {size_mb:.1f} МБ")

        model = YOLO(str(model_path))
        try:
            info = model.info(verbose=False)  # (n_layers, n_params, n_grads, gflops)
            n_params = info[1]
            gflops   = info[3]
        except Exception:
            n_params, gflops = -1, -1

        print(f"  Параметров: {n_params/1e6:.2f} M  |  GFLOPs: {gflops:.1f}\n")

        print("  [1/2] Чистый инференс (640×640, синтетический кадр)...")
        pure = bench_pure_inference(model)
        print(f"        median   : {fmt_ms(pure['median_ms']):>10}  →  {fmt_fps(pure['fps']):>10}")
        print(f"        mean     : {fmt_ms(pure['mean_ms']):>10}")
        print(f"        P95      : {fmt_ms(pure['p95_ms']):>10}")
        print(f"        P99      : {fmt_ms(pure['p99_ms']):>10}")
        print(f"        VRAM peak: {pure['vram_peak_mb']:.0f} МБ")

        for vid in VIDEOS:
            if not vid.exists():
                continue
            print(f"\n  [2/2] Видео-пайплайн: {vid.name}")
            vp = bench_video_pipeline(model, vid)
            print(f"        Разрешение      : {vp['resolution']}, исходный fps={vp['src_fps']:.1f}")
            print(f"        Обработано      : {vp['frames']} кадров за {vp['wall_sec']:.1f} сек")
            print(f"        Throughput      : {fmt_fps(vp['wall_fps'])}")
            print(f"        Latency median  : {fmt_ms(vp['median_ms'])}")
            print(f"        Latency P95     : {fmt_ms(vp['p95_ms'])}")
            print(f"        ~Effective FPS  : {fmt_fps(vp['fps'])}")

            out_rows.append({
                "model": model_name,
                "model_file_mb": round(size_mb, 1),
                "params_M": round(n_params / 1e6, 2),
                "GFLOPs": round(gflops, 1),
                "video": vid.name,
                "resolution": vp["resolution"],
                "frames_processed": vp["frames"],
                "wall_sec": round(vp["wall_sec"], 2),
                "throughput_fps": round(vp["wall_fps"], 2),
                "latency_median_ms": round(vp["median_ms"], 2),
                "latency_p95_ms": round(vp["p95_ms"], 2),
                "pure_inference_median_ms": round(pure["median_ms"], 2),
                "pure_inference_p95_ms":    round(pure["p95_ms"], 2),
                "pure_inference_fps":       round(pure["fps"], 1),
                "vram_peak_mb": round(pure["vram_peak_mb"], 0),
            })

        # очистка GPU между моделями
        del model
        torch.cuda.empty_cache()

    if out_rows:
        out_csv = ROOT / "benchmark_results.csv"
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        print(f"\n\nCSV сохранён: {out_csv}")


if __name__ == "__main__":
    main()
