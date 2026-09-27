#!/usr/bin/env python3

import glob
import json
import pickle
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np

DATA_DIR = (
    Path(__file__).resolve().parent
    / "pi_recorded_data"
)


def decode_frame(frame):

    if frame is None:
        return np.zeros((256, 256, 3), dtype=np.uint8)

    if isinstance(frame, np.ndarray):
        if frame.ndim > 1:
            img = frame
        else:
            img = cv2.imdecode(frame, cv2.IMREAD_COLOR)
    else:
        arr = np.frombuffer(frame, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is None:
        return np.zeros((256, 256, 3), dtype=np.uint8)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    return img


def load_preview_images(episode_dir, num_images=16):

    step_files = sorted(
        glob.glob(str(episode_dir / "step_*.pkl"))
    )

    images = []

    for step_file in step_files[:num_images]:

        try:
            with open(step_file, "rb") as f:
                step = pickle.load(f)

            frames = step["state"].get(
                "camera_frames",
                []
            )

            if len(frames) > 0:
                img = decode_frame(frames[0])
                images.append(img)

        except Exception as e:
            print(f"Fehler bei {step_file}: {e}")

    return images


def show_grid(images, title):

    fig, axes = plt.subplots(
        4,
        4,
        figsize=(10, 10)
    )

    axes = axes.flatten()

    for ax in axes:
        ax.axis("off")

    for ax, img in zip(axes, images):
        ax.imshow(img)

    fig.suptitle(title)

    plt.tight_layout()
    plt.show(block=True)


def review_episode(episode_dir):

    metadata_file = episode_dir / "metadata.json"

    if not metadata_file.exists():
        return

    with open(metadata_file, "r") as f:
        metadata = json.load(f)

    goal_text = metadata.get(
        "goal_text",
        "perform task"
    )

    images = load_preview_images(episode_dir)

    if len(images) > 0:

        show_grid(
            images,
            episode_dir.name
        )

    print()
    print("=" * 80)
    print(f"Episode : {episode_dir.name}")
    print(f"Prompt  : {goal_text}")
    print("=" * 80)

    cmd = input(
        "[ENTER]=ok | e=edit | q=quit : "
    ).strip().lower()

    if cmd == "q":
        raise KeyboardInterrupt

    if cmd == "e":

        new_text = input(
            "Neue Language Instruction:\n> "
        ).strip()

        if len(new_text) > 0:

            metadata["goal_text"] = new_text

            with open(metadata_file, "w") as f:
                json.dump(
                    metadata,
                    f,
                    indent=2
                )

            print("Gespeichert.")


def main():

    for split in ["train", "val"]:

        split_dir = DATA_DIR / split

        if not split_dir.exists():
            continue

        episodes = sorted(
            p for p in split_dir.iterdir()
            if p.is_dir()
        )

        print()
        print(f"=== REVIEWING {split.upper()} ===")

        for episode in episodes:

            try:
                review_episode(episode)

            except KeyboardInterrupt:
                print("\nAbbruch.")
                return

    print("\nAlle Episoden geprüft.")


if __name__ == "__main__":
    main()
