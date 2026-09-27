import argparse
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import jax
import tensorflow_datasets as tfds
from octo.model.octo_model import OctoModel


ACTION_DIM_NAMES = ["dx", "dy", "dz", "roll", "pitch", "yaw", "gripper"]


def preprocess_image(img, size):
    import cv2
    h, w, _ = img.shape
    m = min(h, w)
    sx = (w - m) // 2
    sy = (h - m) // 2
    cropped = img[sy:sy + m, sx:sx + m]
    return cv2.resize(cropped, (size, size))


def build_observation(img_primary_hist, proprio_now, window_size, with_proprio,
                      action_horizon, with_wrist=False):
    """Build an observation dict for one timestep.

    task_completed must match the model's action_horizon (finetuned=50,
    raw octo-base=4), otherwise Octo's shape verification fails. with_wrist
    adds a zero wrist image + pad, which the raw base model expects.
    """
    img_primary = np.stack(img_primary_hist)[None, ...]
    obs = {
        "image_primary": img_primary,
        "timestep": np.arange(window_size, dtype=np.int32)[None, ...],
        "task_completed": np.zeros((1, window_size, action_horizon), dtype=bool),
        "pad_mask_dict": {
            "image_primary": np.ones((1, window_size), dtype=bool),
            "image_wrist": np.ones((1, window_size), dtype=bool) if with_wrist
                           else np.zeros((1, window_size), dtype=bool),
            "timestep": np.ones((1, window_size), dtype=bool),
        },
        "timestep_pad_mask": np.full((1, window_size), True, dtype=bool),
    }
    if with_wrist:
        # raw base expects a wrist image key; feed a zero image (padded out above)
        obs["image_wrist"] = np.zeros((1, window_size, 128, 128, 3), dtype=np.uint8)
    if with_proprio:
        obs["proprio"] = np.tile(np.asarray(proprio_now, dtype=np.float32),
                                 (window_size, 1))[None, ...]
    return obs


def get_unnorm_stats(model, key):
    entry = model.dataset_statistics[key]
    if isinstance(entry, dict) and "action" in entry:
        return entry["action"]
    return entry


def pick_stats_key(model):
    keys = list(model.dataset_statistics.keys())
    if "action" in keys:
        return "action"
    for k in keys:
        sub = model.dataset_statistics[k]
        if isinstance(sub, dict) and "action" in sub:
            return k
    return keys[0]


def run_model_on_episode(model, unnorm_stats, episode, prompt, window_size,
                         with_proprio, action_horizon, with_wrist=False):
    """Return (predicted_actions, ground_truth_actions) for one episode.
    Only the first action of each predicted chunk is used, so the model's
    action_horizon length does not affect the comparison."""
    task = model.create_tasks(texts=[prompt])
    steps = episode["steps"]
    images, states, actions = [], [], []
    for step in steps:
        obs = step["observation"]
        img = obs["image"]
        st = obs["state"]
        act = step["action"]
        img = img.numpy() if hasattr(img, "numpy") else np.asarray(img)
        st = st.numpy() if hasattr(st, "numpy") else np.asarray(st)
        act = act.numpy() if hasattr(act, "numpy") else np.asarray(act)
        images.append(img); states.append(st); actions.append(act)
    images = np.array(images); states = np.array(states); actions = np.array(actions)
    T = len(actions)

    pred_list, true_list = [], []
    img_hist = []
    for t in range(T):
        img_hist.append(preprocess_image(images[t], 256))
        if len(img_hist) < window_size:
            hist = [img_hist[0]] * (window_size - len(img_hist)) + img_hist
        else:
            hist = img_hist[-window_size:]
        if with_proprio:
            pstats = model.dataset_statistics["proprio"]
            proprio_in = (states[t][:3] - pstats["mean"]) / (pstats["std"] + 1e-8)
        else:
            proprio_in = states[t][:3]
        obs = build_observation(hist, proprio_in, window_size, with_proprio,
                                action_horizon, with_wrist=with_wrist)
        pred = model.sample_actions(
            obs, task,
            unnormalization_statistics=unnorm_stats,
            rng=jax.random.PRNGKey(t),
        )
        pred_list.append(np.array(pred[0])[0])   # first action of the chunk
        true_list.append(actions[t])
    return np.array(pred_list), np.array(true_list)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--step", type=int, default=2999)
    ap.add_argument("--compare_base", action="store_true",
                    help="also run octo-base-1.5 and overlay it for comparison")
    ap.add_argument("--base_id", default="hf://rail-berkeley/octo-base-1.5")
    ap.add_argument("--data_dir", default="/home/lego-team-1/data")
    ap.add_argument("--dataset", default="switcher_dataset")
    ap.add_argument("--split", default="val")
    ap.add_argument("--prompt", default="flip the switch from green to red")
    ap.add_argument("--window_size", type=int, default=1,
                    help="window size of the FINETUNED model")
    ap.add_argument("--action_horizon", type=int, default=50,
                    help="action horizon of the FINETUNED model")
    ap.add_argument("--base_window_size", type=int, default=2,
                    help="window size the raw base model expects (octo default 2)")
    ap.add_argument("--base_action_horizon", type=int, default=4,
                    help="action horizon the raw base model expects (octo default 4)")
    ap.add_argument("--out", default="eval_offline.png")
    args = ap.parse_args()

    print(f"Loading dataset {args.dataset} split={args.split} ...")
    ds = tfds.load(args.dataset, split=args.split,
                   data_dir=os.path.expanduser(args.data_dir))
    episodes = list(tfds.as_numpy(ds))
    print(f"Loaded {len(episodes)} episode(s).")

    # ---- finetuned ----
    print(f"\nLoading FINETUNED model from {args.checkpoint} (step={args.step}) ...")
    ft = OctoModel.load_pretrained(args.checkpoint, step=args.step)
    ft_key = "action" if "action" in ft.dataset_statistics else pick_stats_key(ft)
    ft_stats = get_unnorm_stats(ft, ft_key)
    print("finetuned stats key:", ft_key)

    ft_pred, true = [], []
    for ep in episodes:
        p, t = run_model_on_episode(
            ft, ft_stats, ep, args.prompt,
            args.window_size, with_proprio=True,
            action_horizon=args.action_horizon, with_wrist=False)
        ft_pred.append(p); true.append(t)
    ft_pred = np.concatenate(ft_pred); true = np.concatenate(true)
    ft_mae = np.mean(np.abs(ft_pred - true), axis=0)

    base_pred = None
    base_mae = None
    if args.compare_base:
        print(f"\nLoading BASE model {args.base_id} ...")
        base = OctoModel.load_pretrained(args.base_id)
        base_key = pick_stats_key(base)
        base_stats = get_unnorm_stats(base, base_key)
        print("base stats key:", base_key)
        bp = []
        for ep in episodes:
            # raw base uses its own window/horizon and expects a wrist image;
            # it has no proprio input.
            p, _ = run_model_on_episode(
                base, base_stats, ep, args.prompt,
                args.base_window_size, with_proprio=False,
                action_horizon=args.base_action_horizon, with_wrist=True)
            bp.append(p)
        base_pred = np.concatenate(bp)
        base_mae = np.mean(np.abs(base_pred - true), axis=0)

    # ---- report ----
    print("\n=== Mean Absolute Error per action dimension ===")
    header = f"{'dim':8s} {'finetuned':>10s}"
    if base_pred is not None:
        header += f"  {'base':>10s}"
    print(header)
    for i, name in enumerate(ACTION_DIM_NAMES):
        line = f"{name:8s} {ft_mae[i]:10.4f}"
        if base_pred is not None:
            line += f"  {base_mae[i]:10.4f}"
        print(line)
    summary = f"{'xyz_mean':8s} {np.mean(ft_mae[:3]):10.4f}"
    if base_pred is not None:
        summary += f"  {np.mean(base_mae[:3]):10.4f}"
    print(summary)

    # ---- plot xyz ----
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    t_axis = np.arange(len(true))
    for i in range(3):
        ax = axes[i]
        ax.plot(t_axis, true[:, i], label="ground truth", linewidth=2.2, color="black")
        ax.plot(t_axis, ft_pred[:, i], label="finetuned", linewidth=1.6, linestyle="--")
        if base_pred is not None:
            ax.plot(t_axis, base_pred[:, i], label="base", linewidth=1.2,
                    linestyle=":", alpha=0.8)
        ax.set_ylabel(ACTION_DIM_NAMES[i])
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("timestep")
    title = (f"Offline eval: predicted vs ground-truth action\n"
             f"{args.dataset} {args.split} | "
             f"finetuned xyz MAE={np.mean(ft_mae[:3]):.4f}")
    if base_pred is not None:
        title += f" | base xyz MAE={np.mean(base_mae[:3]):.4f}"
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(args.out, dpi=120)
    print(f"\nSaved plot to {args.out}")


if __name__ == "__main__":
    main()