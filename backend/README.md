# Backend

VLA model inference, finetuning pipeline, and kinematics for the LEGO robot arm.

## Overview

This component runs on a workstation/GPU server and handles:
- Loading and running the Octo VLA model
- Inference pipeline (images + instructions → action predictions)
- Inverse kinematics (action predictions → joint angles)
- Sending computed joint angles to the embedded controller
- Finetuning pipeline (training on collected demonstration data)
- Data preprocessing and augmentation

## Architecture

```
Embedded (Pi) --TCP/IP--> Backend Client
                              |
                    ┌─────────┴─────────┐
                    │                   │
              Octo Model          Kinematics
              (Inference)          (IK Solver)
                    │                   │
                    └─────────┬─────────┘
                              |
                        Joint Angles --> Send to Pi
```

## The Octo Model

Octo is an open-source generalist robot policy (transformer-based) pretrained on 800k trajectories from the Open X-Embodiment dataset.

- **Octo-Small**: 27M parameters
- **Octo-Base**: 93M parameters
- Accepts: language instructions OR goal images + camera observations
- Outputs: action chunks via diffusion action head
- Finetuning: ~100 demonstrations, ~5 hours on a single GPU

**Paper**: [Octo: An Open-Source Generalist Robot Policy](https://arxiv.org/abs/2405.12213)  
**Code/Weights**: [https://octo-models.github.io](https://octo-models.github.io)

## Setup

### Prerequisites
- Python 3.9+
- CUDA-capable GPU (for training; inference possible on CPU)
- JAX (Octo is implemented in JAX)

### Installation
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Quick Start
```bash
# Run inference server (connects to Pi)
python -m src.client --host <PI_IP> --port <PORT>

# Run finetuning
python -m src.training.finetune --data_dir ./data --config ./config/finetune.yaml
```

## Project Structure
```
backend/
├── src/
│   ├── client/           # TCP/IP client connecting to Pi server
│   ├── model/            # Octo model loading and inference
│   ├── kinematics/       # IK solver, URDF parsing
│   ├── training/         # Finetuning scripts and data pipeline
│   └── utils/            # Data preprocessing, augmentation
├── config/
│   └── finetune.yaml     # Training hyperparameters
├── data/                 # Training data (gitignored)
├── checkpoints/          # Model checkpoints (gitignored)
├── tests/
├── docs/
├── requirements.txt
└── README.md
```

## References
- [Octo Paper (arXiv:2405.12213)](https://arxiv.org/abs/2405.12213)
- [Octo GitHub](https://github.com/octo-models/octo)
- [Open X-Embodiment Dataset](https://robotics-transformer-x.github.io/)
