import os
import glob
import pickle
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scipy.stats import gaussian_kde

input_dir = "pi_recorded_data"
output_dir = "heatmap_output"

# use last 10% of the episode for approximating the lever position
last_ten_percent = 0.10

def load_step(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def extract_episode_position(episode_path):
    step_files = sorted(glob.glob(os.path.join(episode_path, "step_*.pkl")))

    # Only use the last 10% of the steps to estimate the lever position
    start_idx = int(len(step_files) * (1.0 - last_ten_percent))
    selected_files = step_files[start_idx:]

    ee_positions = []

    for step_file in selected_files:
        try:
            step = load_step(step_file)
            ee = step.get("ee_position", None)

            if ee is None:
                continue

            ee = np.array(ee, dtype=float)
            ee_positions.append(ee)

        except Exception as e:
            print(f"Could not load {step_file}: {e}")

    if not ee_positions:
        return None

    ee_positions = np.array(ee_positions)

    # Compute the mean position of the end-effector for the last 10% of the episode
    mean_pos = np.mean(ee_positions, axis=0)

    return {
        "x": float(mean_pos[0]),
        "y": float(mean_pos[1]),
        "z": float(mean_pos[2]),
        "num_steps": len(step_files),
        "num_used_steps": len(ee_positions),
    }


def load_metadata(episode_path):
    metadata_path = os.path.join(episode_path, "metadata.json")

    if not os.path.exists(metadata_path):
        return {}

    try:
        with open(metadata_path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def collect_episode_positions():
    results = []

    episode_dirs = [
        os.path.join(input_dir, d)
        for d in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, d))
    ]

    episode_dirs = sorted(episode_dirs)

    for episode_path in episode_dirs:
        episode_name = os.path.basename(episode_path)

        pos = extract_episode_position(episode_path)

        if pos is None:
            print(f"Skipping {episode_name}: couldn't find end-effector position")
            continue

        metadata = load_metadata(episode_path)

        result = {
            "episode": episode_name,
            "goal_text": metadata.get("goal_text", ""),
            "task_id": metadata.get("task_id", ""),
            "estimated_switch_position": pos,
        }

        results.append(result)

    return results


def plot_heatmap(results):
    os.makedirs(output_dir, exist_ok=True)

    xs = np.array([r["estimated_switch_position"]["x"] for r in results])
    ys = np.array([r["estimated_switch_position"]["y"] for r in results])

    plt.figure(figsize=(8, 6))

    if len(xs) < 2:
        print("Not enough points for KDE. Falling back to a scatter plot.")

        plt.scatter(xs, ys, color="tab:blue", s=80)
        plt.xlabel("x in m")
        plt.ylabel("y in m")
        plt.title("Lever Position Distribution")
        plt.grid(True, alpha=0.3)

        output_path = os.path.join(output_dir, "switch_position_single_point.png")
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"Saved scatter plot to {output_path}")
        return

    # create KDE heatmap for smooth density estimation
    values = np.vstack([xs, ys])
    kde = gaussian_kde(values)

    # create grid
    padding = 0.02

    xmin, xmax = 0.0 - padding, 0.4 + padding
    ymin, ymax = -0.4 - padding, 0.4 + padding

    xx, yy = np.mgrid[xmin:xmax:200j, ymin:ymax:200j]

    grid_coords = np.vstack([xx.ravel(), yy.ravel()])
    density = kde(grid_coords).reshape(xx.shape)

    plt.imshow(
        density.T,
        origin="lower",
        extent=[xmin, xmax, ymin, ymax],
        cmap="viridis",
        aspect="equal"
    )

    plt.colorbar(label="Estimated Density")

    plt.xlabel("x in m")
    plt.ylabel("y in m")
    plt.title("Lever Position Distribution (KDE)")

    output_path = os.path.join(output_dir, "switch_position_kde.png")

    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved KDE heatmap to {output_path}")


def save_results(results):
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "episode_switch_positions.json")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)

    print(f"Saved position metadata to {output_path}")


def render_heatmap():
    results = collect_episode_positions()

    print(f"Found {len(results)} valid episodes.")

    save_results(results)
    plot_heatmap(results)