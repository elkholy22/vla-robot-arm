### Meeting — 2026-05-11
**Moderator:** *(Nils)*
**Note-taker:** *(Kholy)*
**Attendees:** all 6 + tutor (Lukas)

#### Agenda
1. Octo inference & kinematics integration
2. Robot build progress
3. Camera setup
4. Manual control & GUI
5. Milestone 1 feedback / plan Milestone 2
6. Git repo & infrastructure
7. Test plan
8. Assign tasks

#### Discussion
* **Octo & Kinematics**
    * Octo outputs a 7-dim end-effector vector; we ignore the rpy part, run kinematics on it, and send joint angles to the Pi
    * Pi-side safety check: movements exceeding manually set min/max angles are not executed
    * action_horizon: Octo returns a chunk of 4 actions; you choose how many to execute per inference
    * action gain factor scales up inferences, since the LEGO motors work better on larger deltas
    * Data collection at ~5 Hz; inference is faster than needed, so running both concurrently is fine
* **Robot Build**
    * Basic structure built Friday; all 3 motors rotate; lower axis turns but still wobbles
    * Weekend plan: raise to a stable level, sort the cables, mount a small camera on top
    * Each motor has a gear reduction for stronger control -> can't command an exact angle, must time the run to reach ~180°
    * Motor PID tuned fairly precisely without load; per-motor calibration likely needed
* **Cameras**
    * Octo expects ~256×256 for the primary cam, ~128×128 for the wrist cam; webcams bottom out at 640×480
    * Different resolutions are acceptable since the model can be re-finetuned on our own data
    * Leaning toward a single stationary 3rd-person camera (like RT-1 / Google-robot setups) over a wrist cam
* **Manual Control**
    * Motors currently driven by a keyboard script; want a proper GUI for control, data collection, and live camera view
    * Idea to integrate kinematics for finer control (possibly a game controller)
    * Asynchronous data reading not started yet
* **Test Plan & Quality**
    * Test plan is now a central deliverable; tie it to the kinematics work
    * Requirement candidate: actual motor position saved on shutdown (which motor, how far, where the limits are)
* **Milestone & Orga**
    * Decide this week who presents at Milestone 2 and pick topics; roles expand after Milestone 2

#### Decisions
* **Communication** Use sockets for Pi <-> model (IP-based); Integration Manager will formalize the protocol.
* **Cameras** Single stationary 3rd-person camera; resolution can vary since the model is re-finetuned on our data.
* **Git Workflow** One feature branch per issue, merged via merge requests.
* **Weekly Goal** Get the robot to a stable, testable state and start data-collection prep.

#### Action Items
| Task | Owner | Deadline |
| ------ | ------ | ------ |
| Stabilize robot (raise level, fix lower axis, cables, mount camera) | Adrian & Andreas | 2026-05-18 |
| Build manual control GUI | Adrian | 2026-05-18 |
| Set up CI + infrastructure / code base | Kholy | 2026-05-25 |
| Define communication protocol | Waleed | 2026-05-18 |
| Write test plan | Johannes & Adrian | 2026-05-25 |
| Prepare data collection | Nils, Waleed | 2026-05-18 |

#### Next Meeting
*   **Date:** 2026-05-18
*   **Moderator:** Johannes
*   **Note-taker:** Nils
