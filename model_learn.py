from ultralytics import YOLO
import os
import cv2
import numpy as np
import torch
import yaml
import shutil
import random
from pathlib import Path
from ultralytics import YOLO
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
from tqdm import tqdm
import pandas as pd

device = 'cpu'
if torch.backends.mps.is_available():
    device = 'mps'
elif torch.cuda.is_available():
    device = 'cuda'
print(f"Using device: {device}")


def prepare_dataset(root="./data"):
    for split in ['train', 'val', 'test']:
        img_dir = os.path.join(root, split, 'images')
        label_dir = os.path.join(root, split, 'labels')

        if not os.path.exists(img_dir):
            print(f"Warning: {img_dir} not found")
        if not os.path.exists(label_dir):
            print(f"Warning: {label_dir} not found")

        images = [f for f in os.listdir(img_dir) if f.endswith(('.jpg', '.jpeg', '.png'))] if os.path.exists(
            img_dir) else []
        labels = [f for f in os.listdir(label_dir) if f.endswith('.txt')] if os.path.exists(label_dir) else []

        print(f"{split}: {len(images)} images, {len(labels)} labels")

    data_yaml = {
        'path': os.path.abspath(root),
        'train': 'train/images',
        'val': 'val/images',
        'test': 'test/images',
        'nc': 2,
        'names': ['smoke', 'fire']
    }

    yaml_path = os.path.join(root, 'data.yaml')
    with open(yaml_path, 'w') as f:
        yaml.dump(data_yaml, f, default_flow_style=False)

    print(f"\nCreated {yaml_path}")
    print("Dataset structure is ready for YOLO!")

    return yaml_path


def visualize_samples(data_root='./data', num_samples=5):
    colors = {
        0: (255, 0, 0),
        1: (128, 128, 128)
    }

    fig, axes = plt.subplots(1, num_samples, figsize=(20, 4))

    train_img_dir = os.path.join(data_root, 'train', 'images')
    train_label_dir = os.path.join(data_root, 'train', 'labels')

    images = [f for f in os.listdir(train_img_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    samples = random.sample(images, min(num_samples, len(images)))

    for idx, img_file in enumerate(samples):
        img_path = os.path.join(train_img_dir, img_file)
        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, _ = img.shape

        label_file = img_file.replace('.jpg', '.txt').replace('.jpeg', '.txt').replace('.png', '.txt')
        label_path = os.path.join(train_label_dir, label_file)

        if os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(float(parts[0]))
                        x_center = float(parts[1])
                        y_center = float(parts[2])
                        width = float(parts[3])
                        height = float(parts[4])

                        x1 = int((x_center - width / 2) * w)
                        y1 = int((y_center - height / 2) * h)
                        x2 = int((x_center + width / 2) * w)
                        y2 = int((y_center + height / 2) * h)

                        color = colors.get(class_id, (0, 255, 0))
                        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

                        label = 'fire' if class_id == 1 else 'smoke'
                        cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        axes[idx].imshow(img)
        axes[idx].set_title(f'{img_file}')
        axes[idx].axis('off')

    plt.tight_layout()
    plt.savefig('dataset_samples.png', dpi=150, bbox_inches='tight')
    plt.show()


visualize_samples('./data', num_samples=5)

