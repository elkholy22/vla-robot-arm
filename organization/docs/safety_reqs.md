**Safety requirements:**

Preventing damage to the components:
- leave the motor setting on that makes them turn off when they are stalled, e.g. because they are blocked by an obstacle
- before running scripts that control the motor, pay extra attention to whether the angles are correct and the correct motor is controlled
- before turning the motors on, make sure that no part can be exposed to unusually high loads (e.g. through the lever effect)
- keep all cables far away from moving parts, and do put them under mechanical stress
- define a maximum trajectory deviation threshold: interrupt execution if the end-effector leaves the expected motion corridor

Preventing injury with the LEGO model:
- keep especially the joints clear from fingers and long hair and only touch the robot when its turned off
- before running the software on, check whether you or any team member could be in range of moving parts

VLA-specific:
- be aware that the VLA may misidentify the lever or execute the right motion with wrong parameters under changed lighting, occlusion, or background conditions. 
- after execution, check that the lever state matches the expected outcome, do not allow the robot to retry autonomously if it doesn't
- after fine-tuning or changing the VLA model, its safety and accuracy should be evaluated again

For a scaled up robot, the following safety requirements apply:
- the perimeter around the robot should be kept inaccessible for humans while the robot is running, to prevent collision and injury
- after any unplanned stop or emergency stop, resumption requires explicit human authorization
- if the switch the robot flips is connected to any downstream machine, it should be prevented that the robot software can accidentally make the robot flip the switch again when its left running on its own. 
- depending on what the switch controls, it should be assumed that the robot could make mistakes or break the switch, and further negative consequences of this should be prevented