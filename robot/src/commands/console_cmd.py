import logging
import queue
import threading
from typing import Optional, List
from commands.command_parser import CommandParser, CommandParserError
from core.config_loader import update_offset

logger = logging.getLogger("console_cmd")

class ConsoleCmdExecutor:
    def __init__(self, arm, ui, vla_manager=None, lease_manager=None, controller=None):
        self.arm = arm
        self.ui = ui
        self.vla = vla_manager
        self.lease = lease_manager
        self.controller = controller
        self.parser = CommandParser(add_help=True)
        self._init_commands()
        
        # Command execution queue and sequential worker
        self.cmd_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _worker_loop(self):
        while True:
            try:
                command_text, client_id, silent = self.cmd_queue.get()
                self._exec_cmd_sync(command_text, client_id, silent)
                self.cmd_queue.task_done()
            except Exception as e:
                logger.error(f"Error in command worker thread: {e}")

    def _init_commands(self):
        # Help and Info
        self.parser.command("help").callback(self._cmd_help)

        # E-Stop and Safety
        self.parser.command("stop").description("Emergency Stop: Halt all motors instantly.").callback(self._cmd_stop)
        self.parser.command("unblock").description("Unblock motor drivers after E-stop safety trigger.").callback(self._cmd_unblock)

        # Homing and Calibration
        self.parser.command("home").description("Calibrate and drive back to URDF absolute zero positions.").callback(self._cmd_home)
        self.parser.command("zero").description("Apply current motor positions as the software joint-zero references.").callback(self._cmd_zero)
        
        self.parser.command("calibrate_mode")\
            .description("Toggle calibration mode to bypass limits and set zero. Usage: calibrate_mode <start|stop>")\
            .argument("action")\
            .callback(self._cmd_calibrate_mode)

        self.parser.command("calibrate")\
            .description("Overwrite persistent calibration offsets in config.json. Usage: calibrate <joint> <offset_deg>")\
            .argument("joint")\
            .argument("offset")\
            .callback(self._cmd_calibrate)

        # Joint & Coordinate Controls
        self.parser.command("move")\
            .description("Move target joint to angle in degrees. Usage: move <joint> <angle> [speed_or_relative] [relative]")\
            .argument("joint")\
            .argument("angle")\
            .argument("speed_or_relative", required=False)\
            .argument("relative", required=False)\
            .callback(self._cmd_move)

        self.parser.command("moveee")\
            .description("Move end-effector to target X Y Z coordinates in meters. Usage: moveee <x> <y> <z> [pwm_scale_or_relative] [relative]")\
            .argument("x")\
            .argument("y")\
            .argument("z")\
            .argument("pwm_scale_or_relative", required=False)\
            .argument("relative", required=False)\
            .callback(self._cmd_moveee)

        self.parser.command("jog")\
            .description("Continuous joint jog. Usage: jog <joint> <direction: -1.0 to 1.0> [scale: 0.0 to 1.0]")\
            .argument("joint")\
            .argument("direction")\
            .argument("scale", required=False)\
            .callback(self._cmd_jog)

        # Dataset Recording
        self.parser.command("capture").description("Toggle recording of dataset episode state logs.").callback(self._cmd_capture)
        self.parser.command("goal")\
            .description("Set language description goal prompt for the dataset episode.")\
            .argument("text", is_vararg=True)\
            .callback(self._cmd_set_goal)

        # Control Leases
        self.parser.command("lease")\
            .description("Acquire or release exclusive control keys. Usage: lease <acquire|release>")\
            .argument("action")\
            .callback(self._cmd_lease)

        # VLA / AI Agent Moderation
        self.parser.command("vla_mode")\
            .description("Set VLA AI command safety gate. Usage: vla_mode <block|moderated|auto>")\
            .argument("mode")\
            .callback(self._cmd_vla_mode)

        self.parser.command("vla_approve").description("Approve current pending VLA action step.").callback(self._cmd_vla_approve)
        self.parser.command("vla_reject").description("Discard current pending VLA action step.").callback(self._cmd_vla_reject)
        self.parser.command("vla_trigger_inference").description("Trigger an on-demand VLA inference request step.").callback(self._cmd_vla_trigger_inference)

    def exec_cmd(self, command_text: str, client_id: str = "Unknown", silent: bool = False) -> None:
        normalized = command_text.strip().lower()
        if (normalized == "stop" or normalized == "unblock" or normalized.startswith("stop ") or 
            normalized.startswith("unblock ") or normalized.startswith("jog ")):
            # Run safety and real-time movement commands immediately in a separate thread so they don't block or lag in queue
            threading.Thread(target=self._exec_cmd_sync, args=(command_text, client_id, silent), daemon=True).start()
        else:
            # Queue command for sequential execution
            self.cmd_queue.put((command_text, client_id, silent))

    def _exec_cmd_sync(self, command_text: str, client_id: str = "Unknown", silent: bool = False) -> None:
        old_silent = getattr(self.ui, "is_silent", False)
        self.ui.is_silent = silent
        try:
            try:
                cmd, args = self.parser.parse(command_text)
            except CommandParserError as e:
                self.ui.log(str(e))
                return

            # Enforce client lease ownership on movement commands
            movement_commands = ["move", "moveee", "jog", "home", "zero", "calibrate_mode"]
            if cmd.name in movement_commands and self.lease:
                if not self.lease.validate_lease(client_id):
                    holder = self.lease.get_holder()
                    self.ui.log(f"Command Denied: Client {client_id} does not hold the lease. Active lease: {holder}")
                    return

            # Run command callback
            try:
                # Map keyword args
                cb_args = {k: v for k, v in args.items() if v is not None}
                # Append dynamic context if requested by callback signature
                import inspect
                sig = inspect.signature(cmd._callback)
                if "client_id" in sig.parameters:
                    cb_args["client_id"] = client_id
                elif "client_ip" in sig.parameters:
                    cb_args["client_ip"] = client_id
                
                cmd._callback(**cb_args)
            except Exception as e:
                err_msg = f"Failed executing '{cmd.name}': {e}"
                logger.exception(err_msg)
                self.ui.log(err_msg)
        finally:
            self.ui.is_silent = old_silent

    # Command Callbacks
    def _cmd_help(self):
        self.ui.log(self.parser.format_help())

    def _cmd_stop(self):
        self.arm.stop_all()
        self.ui.log("Emergency stop activated. All motors coasting.")

    def _cmd_unblock(self):
        self.arm.unblock_pwm()
        self.ui.log("PWM unblocked. Robot arm is operational again.")

    def _cmd_home(self):
        self.ui.log("Starting absolute zero calibration recovery...")
        success, msg = self.arm.go_absolute_zero()
        self.ui.log(msg)

    def _cmd_zero(self):
        self.arm.set_zero()
        self.ui.log("Software zero calibration applied to current pose.")

    def _cmd_calibrate_mode(self, action: str):
        action = action.lower()
        if action == "start":
            self.arm.is_calibrating = True
            self.arm.unblock_pwm()
            self.ui.log("Calibration mode enabled. Joint limits are disabled. Jog freely.")
        elif action == "stop":
            if not getattr(self.arm, "is_calibrating", False):
                self.ui.log("Error: Calibration mode is not active.")
                return
            self.arm.is_calibrating = False
            
            # Save the current absolute encoder positions as the new absolute offsets in config
            import core.config_loader as cl
            config = cl.load_config()
            if "robot" not in config:
                config["robot"] = {}
            if "absolute_offsets" not in config["robot"]:
                config["robot"]["absolute_offsets"] = {}
            
            for axis, motor in self.arm.motors.items():
                cur_aposition = motor.get_aposition()
                config["robot"]["absolute_offsets"][axis] = cur_aposition
                
                # Update in-memory absolute offsets & pos_dict
                self.arm.absolute_offsets[axis] = cur_aposition
                self.arm.pos_dict[f"{axis}_offset"] = cur_aposition
                self.arm.pos_dict[f"{axis}_pos"] = 0.0
                self.arm.pos_dict[f"{axis}_revs"] = 0
                self.arm.targets[axis] = None
                self.arm.jogs[axis] = 0.0
                
            cl.save_config(config)
            self.arm.save_position_data()
            
            # Update the arm's session homing cache values since we have a new zero position
            if hasattr(self.arm, 'session_home_ee'):
                self.arm.session_home_base = self.arm.motor_base.get_position()
                self.arm.session_home_vert = self.arm.motor_vert.get_position()
                self.arm.session_home_ee = self.arm.motor_ee.get_position()
                
            self.ui.log("Calibration mode disabled. New zero references set and saved persistently.")
        else:
            self.ui.log("Error: Usage: calibrate_mode <start|stop>")

    def _cmd_calibrate(self, joint: str, offset: str):
        try:
            joint = joint.upper()
            val = float(offset)
            update_offset(joint, val)
            self.arm.offsets[joint] = val
            self.ui.log(f"Persistent offset updated: joint {joint} = {val}°")
        except ValueError:
            self.ui.log("Error: offset value must be numeric.")

    def _cmd_move(self, joint: str, angle: str, speed_or_relative: Optional[str] = None, relative: Optional[str] = None):
        try:
            j = joint.upper()
            deg = float(angle)
            spd = None
            rel = False
            
            if speed_or_relative is not None:
                val = speed_or_relative.lower()
                if val in ("true", "false", "t", "f", "1", "0"):
                    rel = val in ("true", "t", "1")
                else:
                    spd = float(speed_or_relative)
                    if relative is not None:
                        rel = relative.lower() in ("true", "t", "1")
            
            if self.arm.set_target(j, deg, speed=spd, relative=rel):
                move_type = "relative" if rel else "absolute"
                self.ui.log(f"Driving joint {j} {move_type} by/to {deg}°")
            else:
                self.ui.log(f"Failed: Target joint {j} out of bounds.")
        except ValueError:
            self.ui.log("Error: joint coordinates, speed, and relative flags must be numeric or boolean values.")

    def _cmd_moveee(self, x: str, y: str, z: str, pwm_scale_or_relative: Optional[str] = None, relative: Optional[str] = None):
        try:
            val_x = float(x)
            val_y = float(y)
            val_z = float(z)
            
            scale = None
            rel = False
            
            if pwm_scale_or_relative is not None:
                val = pwm_scale_or_relative.lower()
                if val in ("true", "false", "t", "f", "1", "0"):
                    rel = val in ("true", "t", "1")
                else:
                    scale = float(pwm_scale_or_relative)
                    if relative is not None:
                        rel = relative.lower() in ("true", "t", "1")
            
            self.ui.log(f"Solving inverse kinematics for EE coordinate ({val_x}, {val_y}, {val_z})...")
            if hasattr(self.arm, "move_end_effector_to"):
                success, msg = self.arm.move_end_effector_to([val_x, val_y, val_z], scale, relative=rel)
                self.ui.log(msg)
            else:
                self.ui.log("Inverse kinematics solver not supported on current arm object.")
        except ValueError:
            self.ui.log("Error: coordinates, scales, and relative flags must be numeric or boolean values.")

    def _cmd_jog(self, joint: str, direction: str, scale: Optional[str] = None):
        try:
            j = joint.upper()
            d = float(direction)
            s = float(scale) if scale else 1.0
            if self.arm.set_jog(j, d, s):
                if not getattr(self.ui, "is_silent", False) or d == 0.0:
                    self.ui.log(f"Jogging joint {j} at velocity {d} (scale={s})")
            else:
                if not getattr(self.ui, "is_silent", False):
                    self.ui.log(f"Jog failed for joint {j}.")
        except ValueError:
            self.ui.log("Error: jog parameters must be numeric.")

    def _cmd_capture(self):
        if self.controller:
            is_capturing = self.controller.toggle_capture()
            self.ui.log(f"Recording state changed: is_capturing={is_capturing}")
        else:
            self.ui.log("Dataset recorder not active.")

    def _cmd_set_goal(self, text: List[str]):
        goal_prompt = " ".join(text)
        if self.controller:
            self.controller.set_goal_text(goal_prompt)
            self.ui.log(f"Dataset goal instruction set to: '{goal_prompt}'")
        else:
            self.ui.log(f"Goal set (no recorder active): '{goal_prompt}'")

    def _cmd_lease(self, action: str, client_id: str = "Unknown"):
        action = action.lower()
        if not self.lease:
            self.ui.log("Control lease manager is not active.")
            return

        if action == "acquire":
            if self.lease.acquire_lease(client_id):
                self.ui.log(f"Control Lease successfully locked to client {client_id}.")
            else:
                holder = self.lease.get_holder()
                self.ui.log(f"Failed to acquire lease. Active holder: {holder}")
        elif action == "release":
            if self.lease.release_lease(client_id):
                self.ui.log(f"Control Lease released from client {client_id}.")
            else:
                holder = self.lease.get_holder()
                self.ui.log(f"Failed to release. Lease is held by: {holder}")
        else:
            self.ui.log("Error: Usage: lease <acquire|release>")

    def _cmd_vla_mode(self, mode: str):
        mode = mode.lower()
        if self.vla:
            if self.vla.set_mode(mode):
                self.ui.log(f"VLA safety mode updated: {mode.upper()}")
            else:
                self.ui.log("Error: mode must be one of: block, moderated, auto")
        else:
            self.ui.log("VLA integration manager is not active.")

    def _cmd_vla_approve(self):
        if self.vla:
            success, msg = self.vla.approve_pending()
            self.ui.log(msg)
        else:
            self.ui.log("VLA integration manager is not active.")

    def _cmd_vla_reject(self):
        if self.vla:
            success, msg = self.vla.reject_pending()
            self.ui.log(msg)
        else:
            self.ui.log("VLA integration manager is not active.")

    def _cmd_vla_trigger_inference(self):
        if self.vla:
            success, msg = self.vla.trigger_inference()
            self.ui.log(msg)
        else:
            self.ui.log("VLA integration manager is not active.")
