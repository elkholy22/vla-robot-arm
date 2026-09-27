# List of responsibilities:

## Abdelrahman Khaled Mansour M. Elkholy:
 
- Functions and Concepts:
 
	Finetuning & Evaluation:
	- Adapted the Octo finetuning pipeline to our task (configurable window size and action horizon, unnormalized gripper, added proprioception input) and wrote the onecommand Docker wrapper (run_finetune.sh) for reproducible training runs that runs inside a tmux session.
	- Integrated the DiffusionActionHead into the pipeline, replacing L1 head, and set up the optimizer to match Octo's recipe.
	- Set up the Weights & Biases integration and a full validation split evaluation logging loss and an actio -accuracy metric for tracking training and selecting checkpoints.
	- Ran and compared multiple training configurations (small vs base, short vs long action horizon, with-wrist vs primary-only) to find what works best for the task.
	- Built an offline evaluation script (eval_offline.py) comparing a finetuned checkpoint against base Octo on the validation set, showing finetuning measurably improves action predictions.
 
	Inference:
	- Reworked the inference client (cln.py) onto a WebSocket connection to the Web-UI, fetching frames/telemetry and sending the model's Cartesian outputs as movement targets (Web-UI handles the IK).
	- Implemented Receding Horizon Control (RHC) so the arm executes a configurable horizon of predicted steps before reinferring, since executing a single step is insufficient to complete the motion.
	- Extended the OctoWrapper to run all three model modes (base, small, finetuned) through one pipeline: added proprioception handling, a model-agnostic action-statistics lookup, and configurable observation window/horizon.
	- Ran live inference on the physical robot arm with all three models, with the finetuned model driving the arm toward the lever.
	- Contributed to writing camera logic
 
- Technical Manager Contributions (early/mid/late):
 
	- Early: Set up the Git infrastructure and defined the polyrepo structure (separate robot and backend repos); established the branch-per-issue + merge-request workflow on a protected main; created the initial GitLab CI/CD pipeline.
	- Mid: Built the Docker environment for training/inference (JAX/Octo/Pinocchio) with GPU compatibility on the real hardware; set up the container registry with Kaniko image builds; expanded the CI into build -> verify stages (image build, lint, env-check with a syntax check of core files); maintained the branch/MR workflow.
	- Late: Added the deploy stage on the self-hosted themachine runner (verifies the deployed image sees the GPU on real hardware); rebased branches that hadn't been properly linearized onto main while keeping in-progress feature branches intact; kept the pipeline green.
 

## Andreas Flohr:

- Functions and Concepts:
	- Design & Build Robot (v1 and v2 building session)
	- Foundation of the robot server (Fast API server, with basic structure)
	- Command parser and executer (For command based comunication between clients and server)
	- Frontend (Web control panel and dataset renderer)
	- Fixed and reworked Kinematics and Inverse Kinematics (A pinoccio based, Damped Least Squares Kinematic for better ee movment)
	- Implemented and tuned PID position control for all three motors with Waleed
	- Collected fine-tuning data (Work as a teleoperator to collect the datasets for fine-tuning)

- Project Manager Contributions (early/mid/late): 
	- Early:
		- assigned initial work packages (meetings to plan the robot goal, robot building sessions, protocols and requirements definitions, rough Gantt chart schedule)
		- created an initial Gantt chart using Mermaid (see README.md and Issue #5)
		- defined requirements (see issue board and requirements.md)
	- Mid:
		- Keep gantt chart up to date
		- Distribute new tickets, on monday meetings
		- Adjusted issues and reassigned tasks if and as needed
		- Resolved internal team disagreements and proposed effective solutions
	- Late:
		- Keep gantt chart up to date
		- Distribute new tickets, on monday meetings
	- Semester: 
		- throughout the semester, we regularly checked who was available and when, and then coordinated meetings whenever team collaboration was needed.

### Nils and I split all project manager tasks equally (50/50), and we consulted with each other on an ongoing basis.

## Johannes Hammermann:

- Functions and Concepts: 

	- Examined movement behavior using different BuildHat functions, e.g. how the built-in software PID works and how position information is obtained from the absolute encoders, by writing a first python script. 
	- Worked on calibrating the zero-position with Waleed, so the safety limits are adhered to (my code contribution: 20%, his: 80%). 
	- Measured the robot to define good safety limits and write geometry.urdf file for IK/FK using Pinocchio (limits and urdf were changed slightly later, so my contribution: 90%). 
	- Changed how movement is done through frontend (using PWM commands), which strongly improved performance. 			- Added realtime robot preview and done some small fixes in the frontend (overall contribution in current frontend: about 20-30%). 
	- Added a function for moving towards certain xyz-coordinates which could be used to execute movements from Octo outputs.

- Quality Manager Contributions (early/mid/late): Examining encoders and defining safety limits (early), suggesting improvements to zero calibration for better safety and reliability (mid), refactoring and deleting old test files to avoid duplications and merging branches to keep main branch up-to-date (mid & late). Code styling was checked automatically by Gitlab. Added the frontend robot preview to help verify the current calibration, ensuring quality of the recorded coordinates. Ensuring Octo adheres to safety limits by writing the movement execution function accordingly (late).

## Waleed Khaled Fahmy Mohammed: 

- Functions and Concepts:
	- Robot design & construction
	- Designed and implemented the robot’s zero-calibration and homing procedures, using stored absolute encoder references for initial recovery and relative motor-position differences for repeated homing.
	- Configured the calibrated home encoder values and safe joint limits as the shared reference for hardware and software.
	- Integrated homing and calibration into the web UI, enabling complete frontend-to-hardware control.
	- Defined the kinematic joint offsets so the physical robot matches the URDF model for FK and IK.
	- Developed a motor direction validation script to ensure physical joint motion follows the URDF convention.
	- Implemented and tuned closed-loop PID position control for all three motors with Andreas.
	- Proposed replacing L1ActionHead with DiffusionActionHead in the VLA pipeline based on the Octo paper, significantly improving inference quality.
	- Collected data for finetuning.

- Integration Manager Contributions (early/mid/late): 
	- early: Defined the initial system architecture, identified the main software components, and selected HTTP and WebSocket over TCP/IP for communication.
	- mid: Specified the data exchanged between components and their communication protocols. Defined an incremental integration-test strategy in which each feature was tested individually and then verified with the already integrated components.
	- late: Verified that the definitions of components, exchanged data, and communication protocols remained aligned with the final system in refactor branch.

## Nils Rheinländer:

- Functions and Concepts: 
	- Design and build the robot 
	- Redesign the data capture process using Lucas’s library and apply forward kinematics to capture positions with the help of the calibrated angles
	- Implement the RLDS DatasetBuilder with the necessary Octo configurations 
	- Establish the initial connection between the various backend components (e.g., use commands to move the real robot instead of the mockup) 
	- Collect data across multiple sessions; check, visualize, and transform the data into an RLDS dataset.


- Project Manager Contributions (early/mid/late): 
	- early: 
		- Defined requirements (see issue board) 
		- Created an initial Gantt chart using Mermaid (see README and Issue #5) 
		- Assigned initial work packages (first, protocols and requirements were defined, the robot was built, and a rough schedule was created in the Gantt chart)
	- mid + late: 
		- Updated the Gantt chart whenever changes occurred (e.g., due to the many issues with the movement logic) 
		- Added, distributed, and updated tickets during and after the Monday meetings
		- Dynamically adjusted issues and reassigned tasks as needed 
		- Added and refined project goals (e.g., limiting the scope to a fixed environment and defining fewer static switcher positions for the dataset) 
		- Resolved internal team disagreements and proposed effective solutions

	- In addition, throughout the semester, we regularly checked who was available and when, and then coordinated meetings whenever team collaboration was needed.

### Andreas and I split all project manager tasks equally (50/50), and we consulted with each other on an ongoing basis.

## Adrian Tirpak:

- Functions and Concepts:
	- Robot design & construction
	- Designed robot manual control & coded scripts
		- Designed controller control scheme
		- Created threaded scripts for reading controller inputs, transforming them, and sending them to the Pi server
	- Created episode replay feature, reading & executing recorded data on the robot arm; integrated episode replay into the GUI backend/frontend via server commands
	- Data collection

- Quality Manager Contributions (early/mid/late):
	- Discussion & recommendation of coding style (early)
	- Co-design of safety requirements (early)
	- Designing & creating test plan (early)
	- Code review & handling of merge requests while consulting the responsible members (mid/late)
	- Ensuring main branch stability (mid/late)
	- Designing and detailing manual tests (mid/late)