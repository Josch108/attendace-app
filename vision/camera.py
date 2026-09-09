import cv2
import time
from typing import Generator, Tuple, Union
import numpy as np

class CameraStream:
    """
    Manages video capture from local webcams, external USB cameras, video files, or RTSP network streams.
    Supports dynamic hot-swapping between cameras without restarting the vision pipeline.
    """
    def __init__(self, source: Union[int, str] = 0, width: int = 1280, height: int = 720):
        # Convert string digit to integer if applicable (e.g. "0")
        if isinstance(source, str) and source.isdigit():
            self.source = int(source)
        else:
            self.source = source
            
        self.width = width
        self.height = height
        self.cap = None
        self._fps = 0.0
        self._prev_time = time.time()

    def start(self):
        print(f"[CameraStream] Opening video source: {self.source}...")
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video source: {self.source}")

        # Set resolution for webcam devices
        if isinstance(self.source, int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[CameraStream] Video source started at resolution: {actual_w}x{actual_h}")
        return self

    def switch_source(self, new_source: Union[int, str]) -> bool:
        """
        Safely switches to a new video capture source without terminating the pipeline.
        Returns True if the switch succeeded, False otherwise (retaining previous stream).
        """
        if isinstance(new_source, str) and new_source.isdigit():
            new_source = int(new_source)

        if new_source == self.source and self.cap is not None and self.cap.isOpened():
            return True

        print(f"[CameraStream] Switching camera from source '{self.source}' to '{new_source}'...")
        old_cap = self.cap
        try:
            new_cap = cv2.VideoCapture(new_source)
            if not new_cap.isOpened():
                print(f"[CameraStream] Warning: Could not open camera {new_source}. Retaining current source ({self.source}).")
                return False

            if isinstance(new_source, int):
                new_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                new_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            ret, test_frame = new_cap.read()
            if not ret or test_frame is None:
                print(f"[CameraStream] Warning: Camera {new_source} opened but failed to read frame. Keeping current source.")
                new_cap.release()
                return False

            if old_cap is not None and old_cap.isOpened():
                old_cap.release()

            self.cap = new_cap
            self.source = new_source
            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[CameraStream] Successfully switched to camera '{new_source}' ({actual_w}x{actual_h})")
            return True
        except Exception as e:
            print(f"[CameraStream] Error switching camera source: {e}")
            return False

    def read(self) -> Tuple[bool, np.ndarray]:
        if self.cap is None or not self.cap.isOpened():
            return False, None
            
        ret, frame = self.cap.read()
        if ret:
            # Real-time smoothed FPS calculation
            current_time = time.time()
            dt = current_time - self._prev_time
            if dt > 0:
                self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt) if self._fps > 0 else (1.0 / dt)
            self._prev_time = current_time
            
        return ret, frame

    @property
    def fps(self) -> float:
        return self._fps

    def stream(self) -> Generator[np.ndarray, None, None]:
        while True:
            ret, frame = self.read()
            if not ret:
                break
            yield frame

    def release(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            print("[CameraStream] Video source released.")
        self.cap = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
