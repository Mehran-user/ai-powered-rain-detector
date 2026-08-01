import fcntl
import logging
import os
import struct
import sys
import time

import cv2

logger = logging.getLogger("rain_logger")

_VIDIOC_S_CTRL = 0xC008561C
_V4L2_CID_ILLUMINATORS_1 = 0x00980910
_V4L2_CID_ILLUMINATORS_2 = 0x00980911
_V4L2_CID_FLASH_LED_MODE = 0x009B0001
_V4L2_FLASH_LED_MODE_TORCH = 2
_V4L2_FLASH_LED_MODE_NONE = 0


class CameraError(Exception):
    pass


class Camera:
    def __init__(self, config, sound_player):
        self.device_index = config.camera["device_index"]
        self.width = config.camera["width"]
        self.height = config.camera["height"]
        self.led_wait_seconds = config.camera["led_wait_seconds"]
        self.shutter_wait_seconds = config.camera["shutter_wait_seconds"]
        self.sound_player = sound_player
        self.cap = None

    def capture_sequence(self):
        try:
            self._initialize()
            self._set_led(True)
            time.sleep(self.led_wait_seconds)
            frames = []
            for number in range(1, 4):
                frame = self._capture_frame(number)
                frames.append(frame)
                self.sound_player.play()
                if number < 3:
                    time.sleep(self.shutter_wait_seconds)
            return frames
        finally:
            self._set_led(False)
            self._release()

    def _initialize(self):
        logger.info("Camera initializing (device %d).", self.device_index)
        backend = cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.device_index, backend)
        if not cap.isOpened():
            cap.release()
            raise CameraError(
                f"Camera device {self.device_index} could not be opened."
            )
        if self.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap = cap
        logger.info("Camera initialized.")

    def _capture_frame(self, number):
        if self.cap is None:
            raise CameraError("Camera is not initialized.")
        ok, frame = self.cap.read()
        if not ok or frame is None:
            raise CameraError(f"Failed to capture image {number}/3.")
        logger.info("Captured image %d/3.", number)
        return frame

    def _release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        logger.info("Camera released.")

    def _set_led(self, on):
        if sys.platform != "linux":
            logger.warning("LED control only supported on Linux; skipping.")
            return False
        device = f"/dev/video{self.device_index}"
        if not os.path.exists(device):
            logger.warning(
                "LED control unsupported: device %s not found.", device
            )
            return False
        controls = [
            (_V4L2_CID_ILLUMINATORS_1, 1 if on else 0),
            (_V4L2_CID_ILLUMINATORS_2, 1 if on else 0),
            (
                _V4L2_CID_FLASH_LED_MODE,
                _V4L2_FLASH_LED_MODE_TORCH if on else _V4L2_FLASH_LED_MODE_NONE,
            ),
        ]
        for control_id, value in controls:
            try:
                fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
                try:
                    buf = struct.pack("Ii", control_id, value)
                    fcntl.ioctl(fd, _VIDIOC_S_CTRL, buf)
                finally:
                    os.close(fd)
                logger.info("Camera LED %s.", "on" if on else "off")
                return True
            except OSError:
                continue
        logger.warning("LED control not supported by this camera.")
        return False
