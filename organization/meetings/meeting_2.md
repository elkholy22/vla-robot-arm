### Meeting — 2026-05-04
**Moderator:** Kholy 
**Note-taker:** Waleed 
**Attendees:** all 6

#### Agenda
1. Feedback and review of Milestone 1.
2. Progress on robot construction and stability.
3. Camera placement and resolution requirements.
4. Manual control implementation and interface design.
5. Kinematics (Pinocchio library) and data processing from Octo.
6. Server architecture and communication protocols.
7. Project management, Git workflow, and issue tracking.

#### Discussion
* **Milestone 1 & Organization**
    * Feedback for the Milestone 1 presentation will be provided next week following the meeting.
    * The team discussed everyone's recent contributions, which included building the base and lever, setting up the Raspberry Pi, creating the Gantt chart, and testing motors via SSH.
* **Robot Construction**
    * The basic structure and lower axis of the robot have been assembled, but the lower axis currently wobbles and needs to be stabilized with a better gear combination.
    * The lever was redesigned to be smaller, more compact, and equipped with better grip to prevent it from tipping over when interacted with.
    * The team needs to address cable management moving forward.
* **Camera Setup**
    * The setup will rely on two cameras: a stationary camera for the "shoulder" view and a Pi camera mounted on the robot arm for the "wrist" view.
    * Octo models generally accept image resolutions of 256x256 for the shoulder camera and 128x128 for the wrist camera, which should be sufficient despite the low resolution.
* **Manual Control**
    * Basic manual control of the motors has been successfully implemented using keyboard inputs (WASD).
    * The team discussed creating a web-based graphical user interface (GUI) to make manual control more intuitive and to ease data collection, potentially enabling controller or mouse inputs.
* **Kinematics & Data Processing**
    * The Pinocchio library will be used to calculate kinematics.
    * Forward kinematics must be executed first to update the internal physical model state before running inverse kinematics.
    * The 7-value action vector output from Octo will be truncated. Roll, Pitch, and Yaw (RPY) values will be ignored, and only XYZ coordinates will be converted to joint angles to send to the Pi.
    * The script introduces an "Action Horizon" parameter to determine how many actions to execute per inference, and an "Action Gain" parameter that multiplies delta values to increase movement scale and make the robot less conservative.
    * Data collection will run at approximately 5 Hz, which is intuitively expected to be sufficient for teleoperation and Raspberry Pi constraints.
* **Server Architecture & Communication**
    * The backend model server will communicate with the Raspberry Pi using TCP Sockets via IP addresses.
    * Data payloads will be serialized (e.g., using JSON) for transmission between the backend and the robot.
* **Project Management & Workflow**
    * The team reviewed the GitLab issue board and decided to create working branches directly from issues to prevent merge conflicts on protected branches.
    * Quality managers need to draft a comprehensive test plan, focusing specifically on validating kinematics data to ensure motor angles correspond accurately to real-world positions.

#### Decisions
* **Stabilize Robot:** The primary focus for this week is stabilizing the robot's base and lower axis so data collection can reliably begin.
* **Kinematics Approach:** Strip RPY values from the Octo output and rely entirely on inverse kinematics to dictate joint angles.
* **Communication:** Utilize TCP Sockets via IP addressing for the connection between the model server and the Pi.
* **Control Interface:** Build a web-based GUI for manual control and efficient data collection rather than relying on command-line scripts.

#### Action Items
| Task | Owner | Deadline |
| ------ | ------ | ------ |
| Update Gantt chart | Nils, Andreas | 2026-05-11|
| Choose communication protocols / Test server connection | Waleed | 2026-05-11|
| Stabilize and finalize robot build | Nils, Johannes | 2026-05-11|
| Create test plan (focus on kinematics validation) | Johannes, Adrian | 2026-05-11|
| Implement and validate Kinematics | Johannes | 2026-05-11|
| Build GUI for manual robot control | Adrian | 2026-05-11|
| Set up Git workflow and Continuous Integration | Kholy | 2026-05-11|

#### Next Meeting
*   **Date:** 2026-05-11
*   **Moderator:** Nils
*   **Note-taker:** Kholy
