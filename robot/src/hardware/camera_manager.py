import io
import os
import glob
import logging
import threading
import time
import numpy as np
from typing import Dict, Optional, List, Any

# Limit libcamera to only probe Raspberry Pi CSI camera pipeline handlers.
# This prevents it from probing UVC (USB) cameras, which causes "Device or resource busy"
# conflicts when OpenCV has already opened the USB camera.
os.environ["LIBCAMERA_PIPELINES_MATCH_LIST"] = "rpi/vc4,rpi/unicam,raspberrypi"

logger = logging.getLogger("camera_manager")

try:
    import cv2
    HAVE_OPENCV = True
except ImportError:
    HAVE_OPENCV = False
    cv2 = None

try:
    from picamera2 import Picamera2
    HAVE_PICAMERA2 = True
except ImportError:
    HAVE_PICAMERA2 = False
    Picamera2 = None

# Global reference to an existing Picamera2 instance (e.g., from HardwareManager)
_global_picamera2_instance = None
_registered_cameras = {}  # slot_idx/device_id -> camera instance mapping

def set_picamera2_instance(picam2_instance):
    """Register an existing Picamera2 instance to avoid creating duplicates."""
    global _global_picamera2_instance
    _global_picamera2_instance = picam2_instance
    logger.info(f"Registered global Picamera2 instance: {picam2_instance}")

def register_camera(device_id: int, camera):
    """Register a camera instance for a specific device ID."""
    global _registered_cameras
    _registered_cameras[device_id] = camera
    logger.info(f"Registered camera for device {device_id}: {camera}")

def get_registered_camera(device_id: int):
    """Get a registered camera instance by device ID."""
    return _registered_cameras.get(device_id)

_working_cameras_cache = None
_camera_sources_cache = None
_last_scan_time = 0.0

def get_working_cameras() -> List[str]:
    """Scan and return a list of all working /dev/video* paths (cached for 10s)."""
    global _working_cameras_cache, _last_scan_time
    if not HAVE_OPENCV:
        return []
    
    now = time.monotonic()
    if _working_cameras_cache is not None and (now - _last_scan_time < 10.0):
        return _working_cameras_cache
    
    devices = sorted(glob.glob("/dev/video*"))
    working_devices = []
    
    for dev in devices:
        # Skip metadata and non-capture V4L2 subdevices by checking their sysfs index
        base_name = os.path.basename(dev)
        index_file = f"/sys/class/video4linux/{base_name}/index"
        if os.path.exists(index_file):
            try:
                with open(index_file, "r") as f:
                    index_val = f.read().strip()
                if index_val != "0":
                    continue # Skip metadata/control subnodes
            except Exception:
                pass

        # Also skip any Raspberry Pi internal platform/CSI cameras to avoid blocking libcamera/Picamera2
        is_platform_cam = False
        name_file = f"/sys/class/video4linux/{base_name}/name"
        if os.path.exists(name_file):
            try:
                with open(name_file, "r") as f:
                    name_val = f.read().strip().lower()
                skip_keywords = ["unicam", "bcm2835", "hevc", "codec", "isp", "meta", "imx", "ov56", "ov88"]
                if any(kw in name_val for kw in skip_keywords):
                    is_platform_cam = True
            except Exception:
                pass

        device_symlink = f"/sys/class/video4linux/{base_name}/device"
        if os.path.exists(device_symlink):
            try:
                real_path = os.path.realpath(device_symlink).lower()
                if "platform" in real_path or "soc" in real_path or "unicam" in real_path:
                    is_platform_cam = True
            except Exception:
                pass

        if is_platform_cam:
            continue

        try:
            # Attempt to open and capture a single test frame
            cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    working_devices.append(dev)
            cap.release()
        except Exception:
            continue
            
    _working_cameras_cache = working_devices
    return working_devices


def get_camera_sources() -> List[Dict[str, Any]]:
    """Scan and return a list of available camera sources mapped to slots (Slot 0: Webcam, Slot 1: Pi Cam)."""
    global _camera_sources_cache, _last_scan_time
    now = time.monotonic()
    if _camera_sources_cache is not None and (now - _last_scan_time < 10.0):
        return _camera_sources_cache
        
    usb_cams = get_working_cameras()
    sources = []
    
    # Slot 0: USB Webcam (Top View Camera)
    if usb_cams:
        sources.append({"type": "opencv", "path": usb_cams[0]})
    else:
        # Fallback default so slot 0 exists and fails gracefully to placeholder if offline
        sources.append({"type": "opencv", "path": "/dev/video0"})
        
    # Slot 1: Raspberry Pi Camera (Wrist Camera)
    if HAVE_PICAMERA2:
        sources.append({"type": "picamera2", "path": "picamera2"})
    else:
        # If second USB camera exists, use it as Slot 1 fallback when not on a Pi
        if len(usb_cams) > 1:
            sources.append({"type": "opencv", "path": usb_cams[1]})
        else:
            sources.append({"type": "opencv", "path": "/dev/video1"})
        
    _camera_sources_cache = sources
    _last_scan_time = now
    return sources


_placeholder_cache = {}

def generate_placeholder_frame(slot_idx: int) -> bytes:
    """Generates a clean JPG placeholder when a camera is offline or OpenCV is missing."""
    if slot_idx in _placeholder_cache:
        return _placeholder_cache[slot_idx]
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (640, 480), color=(18, 20, 26))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 630, 470], outline=(40, 50, 65), width=2)
        draw.line([10, 10, 630, 470], fill=(25, 30, 40), width=1)
        draw.line([10, 470, 630, 10], fill=(25, 30, 40), width=1)

        try:
            title_font = ImageFont.load_default(size=22)
            sub_font = ImageFont.load_default(size=16)
        except Exception:
            title_font = None
            sub_font = None

        name = "Top View Camera" if slot_idx == 0 else "Wrist Camera"
        draw.text((320, 220), f"{name} (Slot {slot_idx})", fill=(200, 200, 200), anchor="mm", font=title_font)
        draw.text((320, 255), "FEED OFFLINE / CAMERA NOT CONNECTED", fill=(120, 130, 150), anchor="mm", font=sub_font)

        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        res = buf.getvalue()
        _placeholder_cache[slot_idx] = res
        return res
    except Exception:
        # Static black fallback JPEG
        import base64
        res = base64.b64decode(
            b'/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA='
        )
        _placeholder_cache[slot_idx] = res
        return res


class CameraReader:
    def __init__(self, slot_idx: int):
        self.slot_idx = slot_idx
        self.cap = None
        self.picam2 = None
        self.use_picamera2 = False
        self.latest_frame = None
        self.latest_frame_jpeg = None
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.last_success_time = time.monotonic()
        self.active_path = None
        self.failed = False

    def start(self):
        with self.lock:
            if not self.running:
                self.running = True
                self.failed = False
                self.last_success_time = time.monotonic()
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()

    def stop(self):
        with self.lock:
            self.running = False
            self.latest_frame = None
            self.latest_frame_jpeg = None
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

    def _run_picamera2_existing(self, registered_cam):
        """Use an already-opened/registered Picamera2 instance."""
        logger.info(f"Using registered Picamera2 instance for slot {self.slot_idx}")
        self.picam2 = registered_cam
        self.use_picamera2 = True
        self.last_success_time = time.monotonic()

        while self.running:
            try:
                frame = self.picam2.capture_array()
                if frame is not None:
                    # Picamera2 returns frames in format compatible with cv2.imencode directly
                    ret_enc, jpeg = cv2.imencode('.jpg', frame)
                    jpeg_bytes = jpeg.tobytes() if ret_enc else None

                    with self.lock:
                        self.latest_frame = frame.copy() if hasattr(frame, 'copy') else frame
                        self.latest_frame_jpeg = jpeg_bytes
                    self.last_success_time = time.monotonic()
            except Exception as e:
                logger.error(f"Error capturing from registered Picamera2: {e}")
                time.sleep(0.1)
            time.sleep(0.03)

    def _run_opencv_existing(self, registered_cam):
        """Use an already-opened/registered OpenCV capture instance."""
        logger.info(f"Using registered OpenCV camera for slot {self.slot_idx}")
        self.cap = registered_cam
        self.use_picamera2 = False
        self.last_success_time = time.monotonic()

        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue
                
                ret_enc, jpeg = cv2.imencode('.jpg', frame)
                jpeg_bytes = jpeg.tobytes() if ret_enc else None

                with self.lock:
                    self.latest_frame = frame.copy()
                    self.latest_frame_jpeg = jpeg_bytes
                self.last_success_time = time.monotonic()
            except Exception as e:
                logger.error(f"Error reading from registered OpenCV camera: {e}")
                time.sleep(0.1)
            time.sleep(0.03)

    def _init_capture(self) -> bool:
        """Find the camera node matching this slot index and open it."""
        sources = get_camera_sources()
        if self.slot_idx >= len(sources):
            logger.warning(f"Slot {self.slot_idx} is out of bounds for camera sources: {sources}")
            return False
            
        source = sources[self.slot_idx]
        self.active_path = source["path"]
        self.source_type = source["type"]
        
        if self.source_type == "picamera2":
            self.use_picamera2 = True
            return True
            
        # OpenCV initialization
        self.use_picamera2 = False
        if not HAVE_OPENCV:
            return False
            
        logger.info(f"Slot {self.slot_idx} opening OpenCV node path: {self.active_path}")
        try:
            self.cap = cv2.VideoCapture(self.active_path, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                return False
                
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Warmup reads
            for _ in range(3):
                self.cap.read()
                
            self.last_success_time = time.monotonic()
            return True
        except Exception as e:
            logger.warning(f"Error opening camera node {self.active_path}: {e}")
            if self.cap:
                self.cap.release()
                self.cap = None
            return False

    def _run_picamera2(self):
        """Use picamera2 for the Raspberry Pi camera."""
        global _global_picamera2_instance
        try:
            if _global_picamera2_instance is not None:
                self.picam2 = _global_picamera2_instance
                logger.info(f"Using existing global Picamera2 instance for slot {self.slot_idx}")
            else:
                self.picam2 = Picamera2()
                config = self.picam2.create_preview_configuration(
                    main={"format": "RGB888", "size": (640, 480)}
                )
                self.picam2.configure(config)
                self.picam2.start()
                logger.info("Picamera2 started successfully.")
            
            self.last_success_time = time.monotonic()

            while self.running:
                try:
                    frame = self.picam2.capture_array()
                    if frame is not None:
                        # Picamera2 returns frames in format compatible with cv2.imencode directly
                        ret_enc, jpeg = cv2.imencode('.jpg', frame)
                        jpeg_bytes = jpeg.tobytes() if ret_enc else None

                        with self.lock:
                            self.latest_frame = frame.copy() if hasattr(frame, 'copy') else frame
                            self.latest_frame_jpeg = jpeg_bytes
                        self.last_success_time = time.monotonic()
                except Exception as e:
                    logger.error(f"Error capturing from Picamera2: {e}")
                    time.sleep(0.1)
                time.sleep(0.03)

        except Exception as e:
            logger.error(f"Failed to initialize Picamera2: {e}")
            self.failed = True
            # Sleep on initialization failure to prevent tight CPU loops and allow resources to free
            time.sleep(2.0)
        finally:
            # Only stop the camera if we created it (not if we're using the global instance)
            if _global_picamera2_instance is None and self.picam2:
                try:
                    self.picam2.stop()
                except Exception:
                    pass
                try:
                    self.picam2.close()
                except Exception:
                    pass
            self.picam2 = None
            logger.info("Picamera2 stopped.")

    def _run(self):
        logger.info(f"Starting camera reader thread for slot {self.slot_idx}")
        
        # Check if a camera is already registered for this slot first
        registered_cam = get_registered_camera(self.slot_idx)
        if registered_cam is not None:
            if hasattr(registered_cam, 'capture_array'):
                self._run_picamera2_existing(registered_cam)
            elif hasattr(registered_cam, 'read'):
                self._run_opencv_existing(registered_cam)
            return

        while self.running:
            if not hasattr(self, "source_type") or (self.cap is None and not self.use_picamera2):
                # Attempt to initialize
                if not self._init_capture():
                    # Backoff and retry
                    time.sleep(2.0)
                    continue

            if self.use_picamera2:
                self._run_picamera2()
                continue

            # Read frame
            ret, frame = self.cap.read()
            now = time.monotonic()
            
            if ret and frame is not None:
                # Pre-encode frame to JPEG in background thread
                try:
                    ret_enc, jpeg = cv2.imencode('.jpg', frame)
                    jpeg_bytes = jpeg.tobytes() if ret_enc else None
                except Exception as e:
                    logger.error(f"Error encoding frame for slot {self.slot_idx}: {e}")
                    jpeg_bytes = None

                with self.lock:
                    self.latest_frame = frame.copy()
                    self.latest_frame_jpeg = jpeg_bytes
                self.last_success_time = now
            else:
                # If we haven't successfully read a frame for over 1.0s, trigger healing
                if now - self.last_success_time > 1.0:
                    logger.warning(f"[CameraReader] Slot {self.slot_idx} stream frozen. Triggering recovery...")
                    if self.cap:
                        self.cap.release()
                        self.cap = None
                    with self.lock:
                        self.latest_frame = None
                        self.latest_frame_jpeg = None
                    time.sleep(2.0) # wait before re-init scan
            
            time.sleep(0.03) # ~30 FPS

        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info(f"Camera reader thread for slot {self.slot_idx} stopped.")

    def get_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            return self.latest_frame

    def get_frame_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.latest_frame_jpeg


class CameraManager:
    def __init__(self):
        self.readers: Dict[int, CameraReader] = {}
        self.lock = threading.Lock()

    def get_frame(self, slot_idx: int) -> bytes:
        with self.lock:
            if slot_idx not in self.readers:
                self.readers[slot_idx] = CameraReader(slot_idx)
                self.readers[slot_idx].start()
            reader = self.readers[slot_idx]

        jpeg_bytes = reader.get_frame_jpeg()
        if jpeg_bytes is None:
            return generate_placeholder_frame(slot_idx)
        return jpeg_bytes

    def get_raw_frame(self, slot_idx: int) -> Optional[np.ndarray]:
        with self.lock:
            if slot_idx not in self.readers:
                self.readers[slot_idx] = CameraReader(slot_idx)
                self.readers[slot_idx].start()
            reader = self.readers[slot_idx]
        return reader.get_frame()

    def stop_all(self):
        with self.lock:
            for reader in self.readers.values():
                reader.stop()
            self.readers.clear()


camera_manager = CameraManager()
