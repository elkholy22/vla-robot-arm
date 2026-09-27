import wandb
import matplotlib.pyplot as plt
import numpy as np
import tensorflow_datasets as tfds
import argparse
import tqdm
import importlib
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


WANDB_ENTITY = None
WANDB_PROJECT = 'vis_rlds'


parser = argparse.ArgumentParser()
parser.add_argument('dataset_name', help='name of the dataset to visualize')
args = parser.parse_args()

if WANDB_ENTITY is not None:
    render_wandb = True
    wandb.init(entity=WANDB_ENTITY, project=WANDB_PROJECT)
else:
    render_wandb = False


def make_episode_grid(images, max_images=16):
    if len(images) == 0:
        return None

    idx = np.linspace(
        0,
        len(images) - 1,
        min(max_images, len(images)),
        dtype=int,
    )

    selected = [images[i] for i in idx]

    n = len(selected)
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))

    h, w = selected[0].shape[:2]

    grid = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)

    for k, img in enumerate(selected):
        r = k // cols
        c = k % cols

        grid[
            r*h:(r+1)*h,
            c*w:(c+1)*w
        ] = img

    return grid


# dataset
dataset_name = args.dataset_name
print(f"Visualizing data from dataset: {dataset_name}")

module = importlib.import_module(dataset_name)
ds = tfds.load(dataset_name, split='train')
ds = ds.shuffle(100)


# =========================
# 1) IMAGE STRIPS
# =========================
for i, episode in enumerate(ds.take(5)):
    images = []

    for step in episode['steps']:
        images.append(step['observation']['image'].numpy())

    image_strip = np.concatenate(images[::4], axis=1)

    caption = step['language_instruction'].numpy().decode() + \
        ' (temp. downsampled 4x)'

    if render_wandb:
        wandb.log({f'image_{i}': wandb.Image(image_strip, caption=caption)})
    else:
        plt.figure()
        plt.imshow(image_strip)
        plt.title(caption)


# =========================
# 2) ACTION + STATE STATS
# =========================
actions, states = [], []

for episode in tqdm.tqdm(ds.take(500)):
    for step in episode['steps']:
        actions.append(step['action'].numpy())
        states.append(step['observation']['state'].numpy())

actions = np.array(actions)
states = np.array(states)

action_mean = actions.mean(0)
state_mean = states.mean(0)


# =========================
# 3) EPISODE GRID + PRINT
# =========================
for i, episode in enumerate(ds.take(5)):

    front_images = []
    wrist_images = []

    print(f"\n================ EPISODE {i} =================")

    for t, step in enumerate(episode['steps']):

        front_images.append(step['observation']['image'].numpy())
        wrist_images.append(step['observation']['wrist_image'].numpy())

        # end-effector position (x, y, z)
        ee_pos = step['observation']['state'].numpy()

        print(
            f"t={t:03d} | "
            f"x:{ee_pos[0]: .4f}  "
            f"y:{ee_pos[1]: .4f}  "
            f"z:{ee_pos[2]: .4f}"
        )

    caption = step['language_instruction'].numpy().decode()

    front_grid = make_episode_grid(front_images)
    wrist_grid = make_episode_grid(wrist_images)

    if render_wandb:

        wandb.log({
            f'front_camera_episode_{i}': wandb.Image(front_grid, caption=caption),
            f'wrist_camera_episode_{i}': wandb.Image(wrist_grid, caption=caption),
        })

    else:

        plt.figure(f'Front Camera Episode {i}', figsize=(10, 10))
        plt.imshow(front_grid)
        plt.title(caption)
        plt.axis('off')

        plt.figure(f'Wrist Camera Episode {i}', figsize=(8, 8))
        plt.imshow(wrist_grid)
        plt.title(f'Wrist: {caption}')
        plt.axis('off')


# =========================
# 4) STAT PLOTS
# =========================
def vis_stats(vector, vector_mean, tag):
    assert len(vector.shape) == 2
    assert len(vector_mean.shape) == 1
    assert vector.shape[1] == vector_mean.shape[0]

    n_elems = vector.shape[1]
    fig = plt.figure(tag, figsize=(5*n_elems, 5))

    for elem in range(n_elems):
        plt.subplot(1, n_elems, elem+1)
        plt.hist(vector[:, elem], bins=20)
        plt.title(vector_mean[elem])

    if render_wandb:
        wandb.log({tag: wandb.Image(fig)})


vis_stats(actions, action_mean, 'action_stats')
vis_stats(states, state_mean, 'state_stats')


if not render_wandb:
    plt.show()
