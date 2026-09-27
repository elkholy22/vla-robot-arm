# Organization

Project documentation, meeting notes, and presentations for the VLA Finetuning project.

## Project Info

| | |
|---|---|
| **Course** | SESE Projects (EES + MPSEES) |
| **University** | Technische Universität Berlin |
| **Supervisor** | Prof. Dr. Sabine Glesner |
| **TAs** | Willie Szollmann, Lucas Holdermann |
| **Duration** | 3 months (Summer Semester 2026) |
| **ISIS** | https://isis.tu-berlin.de/course/view.php?id=48172 |

## Project Goal

Fine-tune the **Octo** Vision-Language-Action model on a custom LEGO robot arm to perform a specific manipulation task, using only learned control (no handcrafted algorithms).

## Team Roles

| Role | Person | 
|------|--------|
| Project Manager (1/2) | Nils Rheinländer |
| Project Manager (2/2) | Andreas Flohr |
| Technical Manager | Kholy |
| Integration Manager | Waleed Khaled |
| Quality Manager (1/2) | Adrian Tirpak |
| Quality Manager (2/2) | Johannes Hammermann |

## Milestones

| Milestone | Date | Content |
|-----------|------|---------|
| **MS1** | 2026-05-04 | Theory + Concepts (VLAs, finetuning, robot design, task choice) |
| **MS2** | 2026-06-01 | Progress update |
| **MS3** | 2026-06-22 | Progress update |
| **Final** | 2026-07-13 | Live demo + Poster |

## Gantt Chart

![mermaid-diagram-2026-05-16-212037](https://git.tu-berlin.de/-/project/57108/uploads/4b05cbd602738924958f4e6797b218b1/mermaid-diagram-2026-07-11-212126.png)

## Grading

| Component | Points |
|-----------|--------|
| Milestone presentations | 25 |
| Project work / oral consultation | 50 |
| Final presentation | 10 |
| Oral exam | 15 |
| **Total** | **100** |

## Repository Structure
```text
organization/
├── meetings/                  # Weekly meeting notes
│   └── YYYY-MM-DD.md
│
├── presentations/             # Milestone presentations
│   ├── ms1/
│   ├── ms2/
│   ├── ms3/
│   └── final/
│
├── docs/                      # Project documentation
│   ├── protocol_spec.md       # Communication protocol specification
│   ├── requirements.md        # Functional and non-functional requirements
│   ├── responsibilities.md     # Responsibilities of team members
│   ├── safety_reqs.md         # Safety requirements
│   ├── test_plan.md           # System test plan
│   └── test_plan_layers.png   # Illustration of the test-plan layers
│
├── .gitignore                 # Files and directories ignored by Git
├── GIT_WORKFLOW.md            # Git workflow and collaboration guidelines
└── README.md                  # Repository overview and setup instructions
```

## Related Repos

- [robot](https://git.tu-berlin.de/ees-vla-team-1/robot) — Raspberry Pi + Build HAT controller, Kinematics, WebUI
- [backend](https://git.tu-berlin.de/ees-vla-team-1/backend) — Octo model, inference, finetuning
