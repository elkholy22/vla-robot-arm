import json
import os
import sys
from absl import app, flags, logging
import flax
import jax
import optax
import tensorflow as tf
import tqdm
import wandb
import numpy as np

from octo.data.dataset import make_single_dataset
from octo.model.components.action_heads import DiffusionActionHead
from octo.model.components.tokenizers import LowdimObsTokenizer
from octo.model.octo_model import OctoModel
from octo.utils.jax_utils import initialize_compilation_cache
from octo.utils.spec import ModuleSpec
from octo.utils.train_utils import (
    freeze_weights,
    merge_params,
    process_text,
    TrainState,
)

FLAGS = flags.FLAGS

flags.DEFINE_string("pretrained_path", None, "Path to pre-trained Octo checkpoint.")
flags.DEFINE_string("data_dir", None, "Path to finetuning dataset, in RLDS format.")
flags.DEFINE_string("save_dir", None, "Directory for saving finetuning checkpoints.")
flags.DEFINE_integer("batch_size", 16, "Batch size for finetuning.")
flags.DEFINE_integer("train_steps", 50000, "Number of finetuning steps.")
flags.DEFINE_integer("action_horizon", 4, "Number of future actions predicted per step.")
flags.DEFINE_integer("eval_interval", 500, "Run validation every N steps (0 to disable).")
flags.DEFINE_bool("use_wrist", True, "Use both primary and wrist cameras. --nouse_wrist for primary only.")
flags.DEFINE_bool("freeze_transformer", False, "Freeze pre-trained transformer weights.")
flags.DEFINE_bool("augment", True, "Apply image augmentation during training.")
# flags.DEFINE_float("learning_rate", 3e-5, "Peak learning rate after warmup.")
flags.DEFINE_float("learning_rate", 3e-4, "Peak learning rate after warmup.")
flags.DEFINE_float("aug_strength", 1.0, "Scale factor for augmentation magnitudes (0=none, 1=default, 2=aggressive).")
flags.DEFINE_bool("use_proprio", True, "Include joint-angle proprioception as model input.")
flags.DEFINE_integer("window_size", 1, "Number of past timesteps the model observes.")
flags.DEFINE_float("weight_decay", 0.01, "AdamW weight decay (regularization).")
flags.DEFINE_integer("seed", 42, "Random seed for reproducibility / variance studies.")
flags.DEFINE_integer("warmup_steps", 2000, "Linear LR warmup steps before constant LR.")

ACTION_DIM = 7

_BANNER_KEYS = [
    "pretrained_path", "data_dir", "save_dir", "batch_size", "train_steps",
    "action_horizon", "eval_interval", "use_wrist", "freeze_transformer", "augment", "learning_rate", "aug_strength", "use_proprio", "window_size", "weight_decay",
    "seed", "warmup_steps",
]

def _confirm_config():

    while True:

        print("=" * 52)
        print("FINETUNE CONFIG")

        for k in _BANNER_KEYS:
            print(f"  {k:20s} = {FLAGS[k].value}")
        print("=" * 52)

        if not sys.stdin.isatty():
            return
        
        choice = input("[Enter] start   [e] edit a setting   [Ctrl-C] abort: ").strip().lower()

        if choice == "":
            return
        
        if choice == "e":
            key = input("  setting name: ").strip()

            if key in FLAGS:

                try:
                    FLAGS[key].parse(input(f"  new value for {key}: ").strip())

                except Exception as e:
                    print(f"  could not set {key}: {e}")
            else: 
                print(f"  unknown setting: {key}")


def main(_):
    assert (
        FLAGS.batch_size % jax.device_count() == 0
    ), "Batch size must be divisible by device count."

    initialize_compilation_cache()
    tf.config.set_visible_devices([], "GPU")
    _confirm_config()

    wandb.init(name=os.environ.get("WANDB_NAME", "finetune_switcher"), project="octo")

    # Dump the resolved run config next to the checkpoints for reproducibility.
    os.makedirs(FLAGS.save_dir, exist_ok=True)
    run_config = {name: FLAGS[name].value for name in FLAGS}
    with open(os.path.join(FLAGS.save_dir, "config.txt"), "w") as f:
        json.dump(run_config, f, indent=2, default=str)
    wandb.config.update(run_config, allow_val_change=True)

    logging.info("Loading pre-trained model...")
    pretrained_model = OctoModel.load_pretrained(FLAGS.pretrained_path)

    logging.info("Loading finetuning dataset...")

    image_obs_keys = {"primary": "image"}
    if FLAGS.use_wrist:
        image_obs_keys["wrist"] = "wrist_image"

    resize_size = {"primary": (256, 256)}
    if FLAGS.use_wrist:
        resize_size["wrist"] = (128, 128)

    image_augment_kwargs = {}
    if FLAGS.augment:
        # Augmentation settings are based on the original Octo paper
        workspace_aug = dict(
            random_resized_crop=dict(scale=[0.8, 1.0], ratio=[0.9, 1.1]),
            random_brightness=[0.1],
            random_contrast=[0.9, 1.1],
            random_saturation=[0.9, 1.1],
            random_hue=[0.05],
            augment_order=[
                "random_resized_crop", "random_brightness",
                "random_contrast", "random_saturation", "random_hue",
            ],
        )
        wrist_aug = dict(  
            random_brightness=[0.1],
            random_contrast=[0.9, 1.1],
            random_saturation=[0.9, 1.1],
            random_hue=[0.05],
            augment_order=[
                "random_brightness", "random_contrast",
                "random_saturation", "random_hue",
            ],
        )
        image_augment_kwargs = {"primary": workspace_aug}
        if FLAGS.use_wrist:
            image_augment_kwargs["wrist"] = wrist_aug

    dataset_kwargs = dict(
        name="switcher_dataset",
        data_dir=FLAGS.data_dir,
        image_obs_keys=image_obs_keys,
        proprio_obs_key="state",
        language_key="language_instruction",
        action_normalization_mask=[True, True, True, True, True, True, False],
    )
    traj_transform_kwargs = dict(
        window_size=FLAGS.window_size,
        action_horizon=FLAGS.action_horizon,
    )
    frame_transform_kwargs = dict(
        resize_size=resize_size,
        image_augment_kwargs=image_augment_kwargs,
    )

    dataset = make_single_dataset(
        dataset_kwargs=dataset_kwargs,
        traj_transform_kwargs=traj_transform_kwargs,
        frame_transform_kwargs=frame_transform_kwargs,
        train=True,
    )
    train_data_iter = (
        dataset.repeat()
        .unbatch()
        .shuffle(10000)
        .batch(FLAGS.batch_size)
        .iterator()
    )

    text_processor = pretrained_model.text_processor

    def process_batch(batch):
        batch = process_text(batch, text_processor)
        del batch["dataset_name"]
        return batch

    train_data_iter = map(process_batch, train_data_iter)
    example_batch = next(train_data_iter)

    # Validation dataset. Disabled if eval_interval == 0 or no val split.
    # CHANGED: Keep a finite validation dataset instead of creating an
    # infinite `.repeat()` iterator. This lets each eval pass average over
    # the complete validation split instead of logging one noisy batch.
    val_data = None
    if FLAGS.eval_interval > 0:
        try:
            val_dataset = make_single_dataset(
                dataset_kwargs=dataset_kwargs,
                traj_transform_kwargs=traj_transform_kwargs,
                frame_transform_kwargs=dict(resize_size=resize_size),  # no augmentation at eval
                train=False,
            )
            # CHANGED: No `.repeat()` here. Validation should be finite so
            # one evaluation means one pass over the validation set.
            val_data = val_dataset.unbatch().batch(FLAGS.batch_size)
        except Exception as e:
            logging.warning("No validation split available, skipping eval: %s", e)

    config = pretrained_model.config

    if "wrist" in config["model"]["observation_tokenizers"] and not FLAGS.use_wrist:
        del config["model"]["observation_tokenizers"]["wrist"]

    if FLAGS.use_proprio:
        config["model"]["observation_tokenizers"]["proprio"] = ModuleSpec.create(
            LowdimObsTokenizer,
            n_bins=256,
            bin_type="normal",
            low=-2.0,
            high=2.0,
            obs_keys=["proprio"],
        )
    elif "proprio" in config["model"]["observation_tokenizers"]:
        del config["model"]["observation_tokenizers"]["proprio"]

    config["model"]["heads"]["action"] = ModuleSpec.create(
        DiffusionActionHead,
        action_horizon=FLAGS.action_horizon,
        action_dim=ACTION_DIM,
        readout_key="readout_action",
        diffusion_steps=20,
        n_diffusion_samples=1,
    )

    logging.info("Updating model for new observation & action space...")
    model = OctoModel.from_config(
        config,
        example_batch,
        text_processor,
        verbose=True,
        dataset_statistics=dataset.dataset_statistics,
    )
    merged_params = merge_params(model.params, pretrained_model.params)
    model = model.replace(params=merged_params)
    del pretrained_model


    # Octo finetune_config.py: cosine decay with linear warmup
    learning_rate = optax.warmup_cosine_decay_schedule(
        init_value=0.0,
        peak_value=FLAGS.learning_rate,
        warmup_steps=FLAGS.warmup_steps,
        decay_steps=FLAGS.train_steps,
        end_value=0.0,
    )
    tx = optax.chain(
        optax.clip_by_global_norm(1.0),   # gradient clipping (Octo-style stability)
        optax.adamw(learning_rate, weight_decay=FLAGS.weight_decay),
    )
    frozen_keys = model.config["optimizer"]["frozen_keys"]
    if FLAGS.freeze_transformer:
        frozen_keys.append("BlockTransformer_0")
    tx = freeze_weights(tx, model.params, frozen_keys)
    train_state = TrainState.create(
        rng=jax.random.PRNGKey(FLAGS.seed),
        model=model,
        tx=tx,
    )

    def loss_fn(params, batch, rng, train=True):
        bound_module = model.module.bind({"params": params}, rngs={"dropout": rng})
        transformer_embeddings = bound_module.octo_transformer(
            batch["observation"],
            batch["task"],
            batch["observation"]["timestep_pad_mask"],
            train=train,
        )
        action_loss, action_metrics = bound_module.heads["action"].loss(
            transformer_embeddings,
            batch["action"],
            batch["observation"]["timestep_pad_mask"],
            batch["action_pad_mask"],
            train=train,
        )
        return action_loss, action_metrics

    @jax.jit
    def train_step(state, batch):
        rng, dropout_rng = jax.random.split(state.rng)
        (loss, info), grads = jax.value_and_grad(loss_fn, has_aux=True)(
            state.model.params, batch, dropout_rng, train=True
        )
        # add standard training signals (loss, grad norm) to the logged info
        info["loss"] = loss
        info["grad_norm"] = optax.global_norm(grads)
        new_state = state.apply_gradients(grads=grads, rng=rng)
        return new_state, info

    @jax.jit
    def eval_step(state, batch):
        loss, info = loss_fn(state.model.params, batch, state.rng, train=False)
        return info

    logging.info("Starting finetuning...")
    for i in tqdm.tqdm(range(FLAGS.train_steps), total=FLAGS.train_steps, dynamic_ncols=True):
        batch = next(train_data_iter)
        train_state, update_info = train_step(train_state, batch)

        if (i + 1) % 100 == 0:
            update_info = jax.device_get(update_info)
            wandb.log(
                flax.traverse_util.flatten_dict({"training": update_info}, sep="/"),
                step=i,
            )

        if val_data is not None and (i + 1) % FLAGS.eval_interval == 0:
            # Evaluate on the full validation split, averaging all batches.
            val_infos = []
            action_maes = []   # MAE on SAMPLED actions (head comparable metric)
            for val_batch in map(process_batch, val_data.iterator()):
                val_infos.append(jax.device_get(eval_step(train_state, val_batch)))

                # action MAE via sample_actions (comparable across L1/diffusion) 
                # Sample actions and compare to ground-truth (both unnormalized).
                pred_actions = train_state.model.sample_actions(
                    val_batch["observation"],
                    val_batch["task"],
                    unnormalization_statistics=train_state.model.dataset_statistics["action"],
                    rng=jax.random.PRNGKey(i),
                )
                pred = np.asarray(jax.device_get(pred_actions))
                # sample_actions may return (sample_shape, B, horizon, dim); drop leading sample dim
                while pred.ndim > 3:
                    pred = pred[0]
                # pred is now (B, horizon, dim), already unnormalized
                true_actions = np.asarray(jax.device_get(val_batch["action"]))
                # val_batch["action"] is (B, window, horizon, dim); take last window step 
                if true_actions.ndim == 4:
                    true_actions = true_actions[:, -1]
                # ground-truth in the batch is normalized unnormalize to match pred
                stats = train_state.model.dataset_statistics["action"]
                true_unnorm = true_actions * np.asarray(stats["std"]) + np.asarray(stats["mean"])
                # MAE on xyz 
                mae_xyz = float(np.mean(np.abs(pred[..., :3] - true_unnorm[..., :3])))
                action_maes.append(mae_xyz)

            if len(val_infos) > 0:
                mean_val_info = jax.tree_util.tree_map(
                    lambda *xs: sum(xs) / len(xs),
                    *val_infos,
                )
                log_dict = flax.traverse_util.flatten_dict(
                    {"validation": mean_val_info}, sep="/")
                if len(action_maes) > 0:
                    log_dict["validation/action_mae_xyz"] = sum(action_maes) / len(action_maes)
                wandb.log(log_dict, step=i)
            else:
                logging.warning("Validation dataset produced no batches; skipping eval.")

        if (i + 1) % 5000 == 0:
            train_state.model.save_pretrained(step=i, checkpoint_path=FLAGS.save_dir)

    # save final checkpoint at the end of training
    train_state.model.save_pretrained(step=FLAGS.train_steps - 1, checkpoint_path=FLAGS.save_dir)
    logging.info("Finetuning complete. Saved checkpoints to %s", FLAGS.save_dir)


if __name__ == "__main__":
    app.run(main)
