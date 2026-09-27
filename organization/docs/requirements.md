**Goal:** The system shall provide an agile robot  capable of recognizing a lever in its current state and, on command, moving it to the correct position while operating in a dynamic environment.

**Requirements:**

| Functional | Description |
| ------ | ------ |
|     Object Detection   |    The robot shall detect and recognize the lever within its operating environment.    |
|    Object Localization    |    The robot shall determine the precise position and orientation of the detected lever.    |
|    Agile Motion    |    The robot shall move quickly and accurately toward the lever while adapting to changes in its environment.    |
|    Adaptive Lever Flipping    |    The robot shall identify the current lever state and move it into the required position using an appropriate motion.    |
|    Receive & Follow User Commands    |    The robot shall receive user commands and execute the requested lever-flipping action.    |
|    Detect Errors    |    The robot shall detect failed actions, unexpected obstacles, and incorrect lever positions during operation.    |

| Non-Functional | Description |
| ------ | ------ |
|     Reliability   |    The robot shall perform the requested lever-flipping task consistently and with a high success rate.    |
|     Safety (no harm to environment & user)    |    The robot shall operate without causing harm to the user, nearby objects, or the surrounding environment.    |
|    Maintainability    |    The robot’s hardware, software, and trained control model shall be easy to inspect, update, repair, and retrain.    |
|    Scalability    |    The system shall support additional lego robots, commands, and operating environments without requiring a complete redesign.    |