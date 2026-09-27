# Install Python 3.10 via pyenv

```bash
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev libncursesw5-dev \
libffi-dev liblzma-dev
```

```bash
curl https://pyenv.run | bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc && \
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc && \
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
source ~/.bashrc
```

```bash
pyenv install 3.10
pyenv local 3.10
```

# Install Pinocchio and Buildhat

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# Recording, Zeroing, And Coordinates

This section is for frontend users who want to record data through the web UI.

## The One Real Home Pose

The robot has one calibrated physical Home pose. That pose is stored in:

```text
src/web_ui/backend/zero_offsets.json
```

The important field is:

```json
"absolute_offsets": {
  "A": 8,
  "B": -150,
  "C": 112
}
```

Those values are absolute Build HAT encoder angles from `get_aposition()`. They are not frontend simulation offsets and they are not model-space XYZ values. If you want to understand the absolute encoder values for the intended Home pose, read this JSON file directly.

`motor_positions.json` is not the calibration source of truth. It is runtime bookkeeping for counted motor positions and wrap-around state. The backend always re-anchors from `zero_offsets.json` when it performs absolute Home recovery.

## Startup Behavior

When the hardware backend creates `RobotArm`, it:

1. Loads limits from `zero_offsets.json`.
2. Loads existing `motor_positions.json` if present, mainly to detect jumps.
3. Immediately calls `go_absolute_zero()`.

That means normal startup drives the robot to the calibrated absolute Home pose from `zero_offsets.json` and then sets the counted operational positions to zero:

```text
A_pos = 0
B_pos = 0
C_pos = 0
```

The UI joint angles are then derived from `current_pos_dict`:

```text
joint_angle = counted_motor_degrees / gear_ratio
```

So after a successful Home operation, the UI joint angles should read approximately `A=0, B=0, C=0`.

## Home And Recover Zero In The UI

In the web UI, the `Home` button calls the backend absolute-zero recovery function. The console command `home` does the same.

The console command `recover_zero` is just a placeholder and currently also calls the same backend function as `home`. In the UI, `Home` and `recover_zero` are therefore the same kind of action: both run absolute recovery to the JSON Home pose.

This is different from the standalone script:

```text
src/web_ui/backend/recover_zero.py
```

That script loads `zero_offsets.json`, drives the motors to those absolute offsets, and then lets a human manually shift joints by full 360-degree turns if a motor lands in the right absolute encoder phase but the wrong physical wrap. Use that script only when the normal Home/recover action reaches the wrong physical rotation cycle or after a bad physical/offline movement makes the wrap ambiguous. Run it from the backend directory so it finds `zero_offsets.json`.

## Shutdown And Emergency Stops

You do not need to manually press Home before ending the program.

On normal backend shutdown, `RobotArm.safe_shutdown()` already starts `go_absolute_zero()` and then saves position data. Also, the next startup calls `go_absolute_zero()` again from `zero_offsets.json`, so the real calibration does not depend on you manually saving a perfect final pose.

If the program is stopped normally, the code attempts to return Home before releasing motors. If there is a hard power loss or emergency shutdown, the robot may not be physically at Home. In that case, on the next startup the backend still tries absolute recovery from `zero_offsets.json`. If the robot recovers to the wrong 360-degree rotation cycle, use the standalone `recover_zero.py` script for visual verification and manual 360-degree correction.

The web UI emergency stop blocks PWM and coasts the motors. After that, use the console command:

```text
unblock
```

before trying to jog or move again. If you need to re-establish the calibrated pose after unblocking, press `Home`.

## XYZ End-Effector Coordinates

The displayed XYZ end-effector coordinates are calculated by Pinocchio forward kinematics from:

```text
src/web_ui/backend/zeroshot_prototype.xml
```

The backend maps motors to URDF joints like this:

```text
Motor C -> joint1
Motor B -> joint2
Motor A -> joint3
```

The joint angles used for FK come from `current_pos_dict` divided by the gear ratios. No frontend preview offsets are applied to backend FK or IK.

The XYZ coordinates are in the URDF/global robot coordinate frame rooted at `base_link`. They are not relative to the Home end-effector position. At Home, the joint angles are zero, but the end effector still has a non-zero XYZ position because the URDF includes the physical link lengths and offsets.

The `moveee <x> <y> <z> [pwm_scale]` command uses the same coordinate system. With absolute movement enabled in the web backend, those target coordinates are interpreted as URDF/global XYZ coordinates, not Home-relative deltas.

## Recording Data

For web UI recording, the recorder stores calibrated joint angles from `RobotArm.get_joint_angles()` and the backend FK end-effector position from `RobotArm.get_end_effector_position()`.

For the standalone Pi/manual recording path, hardware state now comes from `HardwareManager.read_state()`, which reconstructs counted positions from absolute encoder readings and the configured zero offsets. It should not use raw Build HAT `get_position()` as the recorded joint state.

The frontend kinematic preview may be adjusted using a local frontend-only offset so the schematic visually matches the intended Home posture.