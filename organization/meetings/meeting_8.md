### Meeting — 2026-06-15
**Moderator:** Kholy <br />
**Note-taker:** Waleed  <br />
**Attendees:** all 6

#### Agenda
1. Octo model inference and fine-tuning.
2. Zero-position calibration testing and safety.
3. GUI integration, manual control, and threading issues.
4. Movement fallback plans.
5. Web UI branch merge and repository cleanup.
6. Milestone 3 and final poster planning.
7. Data collection scheduling.

#### Discussion
* **Octo & Fine-Tuning**
    * Inference runs, but autonomous lever-flipping is not yet successful.
    * Fine-tuning script will be deployed using a small test-format dataset.
* **Zero Calibration**
    * Calibration script successfully returns the robot to zero position.
    * Absolute encoder tracking is saved to a JSON offset file to maintain limits.
* **GUI & Manual Control Integration**
    * Camera streaming and video recording work in the backend.
    * Threading issues cause command queue lockups, breaking the E-stop.
* **Movement Fallback**
    * Direct PWM motor power commands bypass sluggish library controllers.
    * Fallback plan is programmatically moving in 1-degree steps if smooth control fails.
* **Hardware Issues**
    * Pi is powered via the Build HAT, dual power inputs are not supported.
* **Git Workflow**
    * Web UI branch must be rebased from main and merged.
    * Clean up main branch by removing obsolete test scripts.
* **Milestone 3 & Final Poster**
    * Next milestone focuses on implementation updates and documenting failed iterations.
    * Final presentation will use a digital DIN A2/A0 poster instead of slides.

#### Decisions
* **Movement Fallback:** Use 1-degree step control if smooth PWM is not working by Wednesday.
* **Git Management:** Rebase, merge Web UI branch, and delete legacy test files.

#### Action Items
| Task | Owner | Deadline |
| ------ | ------ | ------ |
| Deploy fine-tuning script and dataloader | Kholy | 2026-06-22 |
| Rebase, merge Web UI, and clean up main | Adrian, Andreas | 2026-06-22 |
| Fix GUI backend and threading bugs | Andreas | 2026-06-22 |
| Build manual control script and test | Adrian | 2026-06-22 |
| Draft Milestone 3 slides | Johannes, Adrian | 2026-06-22 |
| Conduct physical data collection sessions | Nils, Waleed | 2026-06-22 |

#### Next Meeting
*   **Date:** 2026-06-22
*   **Moderator:** Nils
*   **Note-taker:** Kholy