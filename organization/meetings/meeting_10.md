# Meeting — 2026-06-29

**Moderator:** Johannes
**Note-taker:** Nils
**Attendees:** all 6

## Agenda
1. Review of last week
2. Zero calibration integration
3. Replay functionality
4. Inference and dataset normalization
5. Distributing issues

## Discussion
* Talked about progress from last week
* Discussed the zero calibration approach (see README for the agreed compromise).
* Planned to implement replay functionality.
* Considered integrating the replay feature into the dataset visualizer.
* Discussed connecting inference with the zero calibration pipeline.
* Agreed that the goal should be configurable via the CLI.

## Decisions
* **How should unnormalization be handled?**:
    * Lucas doesn't think so. We just log AI output, and log for tests, but otherwise logging is just for debugging
    * Unnormalize the model output from the normalized range to real robot positions.
    * This can either be done during dataset creation or at inference time, following Lucas' approach.
    * The conversion only needs to be computed once per dataset, unless the dataset itself reaches the robot limits and requires a different normalization.
    * As an initial experiment, the existing WidowX unnormalization can be reused. Lucas already provides an endpoint for this, so it may only require a single function call.
* **Which zero position should be used?**
    * Use Waleed's zero position as the reference.
* **Should the goal be configurable?**
    * The goal should be set via the CLI.


## Action Items
| Task | Owner | Deadline |
|------|-------|----------|
|Validation Replay|Adrian|06.07.26|
|Fix manual control in backend|Johannes|06.07.26|
|Data Collection|Nils|06.07.26|
|GUI additions|Andreas|06.07.26|
|Unnormalization|Kholy & Waleed|06.07.26|
|New Training|Kholy|06.07.26|
|Setup Poster|Johannes|06.07.26|

## Next Meeting
- **Moderator:** Andreas
- **Note-taker:** Adrian