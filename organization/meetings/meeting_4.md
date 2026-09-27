### Meeting — 2026-05-18
**Moderator:** Johannes
**Note-taker:** Nils 
**Attendees:** all 6

#### Agenda
1. Discuss progress from last week
2. Exchange further ideas on manual control
3. Server access is available for testing
4. Discuss further details on fine-tuning
5. Discuss further details on the GUI
6. Discuss the test plan and the CI runner
7. Assign new tasks

#### Discussion
* **Manual Control**
    * Do the final tweaks and see how it can be recorded
    * Reading controller data from the web-gui is still an issue
    * Maybe solve Gear Ratios with limit switches
    * Maybe use target positions instead of angles for manual control
* **Octo & Finetuning**
    * Octo Inference on CPU tested by Kholy; with the Octo Notebook, you can also test it using images from our robot, but fine-tuning must be done via the server
    * Calculate end-effector positions using forward kinematics, then calculate the difference at the end; you could optionally add the joint angles -> Work with delta end positions (include delta joint angles only as an option)
    * The training session is scheduled to take 6–8 hours; please coordinate with the other team beforehand
    * Server access should be working starting today
* **CI/CD Runner & Orga**
    * Willi enabled CI Runner today, but it doesn't support ARM yet, so we might have to skip the compilation step if we're compiling for ARM
    * Willi will be back on Wednesday if any further questions come up


#### Decisions
* **CI/CD Runner** Now that the Runner is ready, we can start working with the CI Runner.
* **Test Plan** Since we're now focusing primarily on coding, there needs to be a test plan.

#### Action Items
| Task | Owner | Deadline |
| ------ | ------ | ------ |
| Prepare 2nd Milestone | Nils, Waleed | 2026-06-01|
| Create Test-Plan | Johannes & Adrian | 2026-05-25|
| CI/CD | Kholy | 2026-05-25|
| Check PI Camera | Kholy | 2026-05-25|
| Check server connection | Kholy & Waleed | 2026-05-25|
| Octo Test | Kholy | 2026-05-25|
| Finish manual robot control and establish GUI connection | Adrian & Andreas | 2026-05-25|
| Prepare data collection | Waleed, Nils | 2026-05-25|

#### Next Meeting
*   **Date:** 2026-05-25 (in Zoom um 10Uhr)
*   **Moderator:** Andreas
*   **Note-taker:** Adrian
