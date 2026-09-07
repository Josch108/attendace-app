from dataclasses import dataclass
from typing import List
import numpy as np
from ultralytics import YOLO

@dataclass
class TrackedPerson:
    track_id: int
    bbox: List[int]  # [x1, y1, x2, y2]
    confidence: float

    @property
    def x1(self) -> int:
        return self.bbox[0]

    @property
    def y1(self) -> int:
        return self.bbox[1]

    @property
    def x2(self) -> int:
        return self.bbox[2]

    @property
    def y2(self) -> int:
        return self.bbox[3]

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)


class PersonTracker:
    """
    Person detector and tracker based on YOLOv8 and ByteTrack.
    """
    def __init__(self, model_name: str = "yolov8n.pt", conf_thresh: float = 0.40):
        print(f"[PersonTracker] Loading YOLO model ({model_name})...")
        self.model = YOLO(model_name)
        self.conf_thresh = conf_thresh
        print("[PersonTracker] Model loaded and configured with ByteTrack.")

    def update(self, frame: np.ndarray) -> List[TrackedPerson]:
        """
        Executes person detection and temporal tracking on a single frame.
        Filters strictly for class 'person' (COCO class 0).
        """
        results = self.model.track(
            source=frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],           # Person class only
            conf=self.conf_thresh,
            verbose=False
        )

        tracked_people = []
        if not results or len(results) == 0:
            return tracked_people

        r = results[0]
        if r.boxes is not None and r.boxes.id is not None:
            boxes = r.boxes.xyxy.cpu().numpy().astype(int)
            track_ids = r.boxes.id.cpu().numpy().astype(int)
            confs = r.boxes.conf.cpu().numpy().astype(float)

            for box, track_id, conf in zip(boxes, track_ids, confs):
                x1, y1, x2, y2 = box.tolist()
                # Ensure coordinates are bounded within frame dimensions
                h, w = frame.shape[:2]
                x1 = max(0, min(x1, w - 1))
                y1 = max(0, min(y1, h - 1))
                x2 = max(0, min(x2, w - 1))
                y2 = max(0, min(y2, h - 1))

                tracked_people.append(
                    TrackedPerson(
                        track_id=int(track_id),
                        bbox=[x1, y1, x2, y2],
                        confidence=float(conf)
                    )
                )

        return tracked_people

    @staticmethod
    def crop_person(frame: np.ndarray, bbox: List[int]) -> np.ndarray:
        x1, y1, x2, y2 = bbox
        return frame[y1:y2, x1:x2]

    @staticmethod
    def crop_head_region(frame: np.ndarray, bbox: List[int]) -> np.ndarray:
        """
        Extracts the upper portion of the bounding box (head/face area)
        to accelerate facial detection and minimize false positive crops.
        """
        x1, y1, x2, y2 = bbox
        h = y2 - y1
        head_y2 = y1 + int(h * 0.45)
        return frame[y1:head_y2, x1:x2]
