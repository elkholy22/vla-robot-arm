import argparse
import random
import shutil
from pathlib import Path


def split_recordings(base_dir: Path, train_ratio: float = 0.9, seed: int = 42):
    base_dir = base_dir.resolve()
    if not base_dir.exists():
        raise FileNotFoundError(f'Base directory not found: {base_dir}')

    episode_dirs = [p for p in base_dir.iterdir() if p.is_dir()
                    and p.name not in ('train', 'val')]
    episode_dirs.sort()
    random.Random(seed).shuffle(episode_dirs)

    train_dir = base_dir / 'train'
    val_dir = base_dir / 'val'
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    n_train = int(len(episode_dirs) * train_ratio)
    train_episodes = episode_dirs[:n_train]
    val_episodes = episode_dirs[n_train:]

    print(f'Found {len(episode_dirs)} episode folders.')
    print(f'Moving {len(train_episodes)} to {train_dir}')
    print(f'Moving {len(val_episodes)} to {val_dir}')

    for ep in train_episodes:
        dst = train_dir / ep.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(ep), str(dst))

    for ep in val_episodes:
        dst = val_dir / ep.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(ep), str(dst))

    print('Split complete.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Split pi recordings into train/val episode folders.')
    parser.add_argument('--base-dir', type=Path, default=Path(__file__).resolve().parent / 'pi_recorded_data',
                        help='Base recording folder that contains episode folders.')
    parser.add_argument('--train-ratio', type=float, default=0.9,
                        help='Fraction of episodes to use for train split.')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for split reproducibility.')
    args = parser.parse_args()

    split_recordings(
        args.base_dir, train_ratio=args.train_ratio, seed=args.seed)
