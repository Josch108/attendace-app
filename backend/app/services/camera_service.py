import sys
import json
import subprocess
from typing import List, Dict, Any, Optional

class CameraService:
    """
    Manages detection, listing, and dynamic switching of video capture devices
    (built-in webcams, external USB cameras, and network streams).
    """
    def __init__(self):
        self._active_camera_id: str = "0"
        self._custom_cameras: Dict[str, Dict[str, Any]] = {}
        self._browser_devices: Dict[str, str] = {}

    def get_system_cameras(self) -> List[Dict[str, Any]]:
        """
        Detects connected cameras using macOS system_profiler or default fallback indices.
        Enriches device names with browser-detected device labels if available.
        """
        detected: List[Dict[str, Any]] = []
        profiler_names: List[str] = []

        # 1. Attempt macOS system_profiler detection
        if sys.platform == "darwin":
            try:
                res = subprocess.run(
                    ["system_profiler", "SPCameraDataType", "-json"],
                    capture_output=True,
                    text=True,
                    timeout=2.0
                )
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    items = data.get("SPCameraDataType", [])
                    for item in items:
                        name = item.get("_name")
                        if name:
                            profiler_names.append(name)
            except Exception:
                pass

        # 2. Build list with detected hardware names or sensible default indices
        num_devices = max(3, len(profiler_names))
        for idx in range(num_devices):
            cid = str(idx)
            is_first = (idx == 0)

            # Determine best display label
            if cid in self._browser_devices:
                name = f"{self._browser_devices[cid]} (Index {cid})"
                cam_type = "external" if not is_first else "builtin"
            elif idx < len(profiler_names):
                raw_name = profiler_names[idx]
                cam_type = "builtin" if any(k in raw_name.lower() for k in ["facetime", "built-in", "internal", "integrated"]) else "external"
                name = f"{raw_name} (Index {cid})"
            else:
                if is_first:
                    name = f"Built-in Camera (Index {cid})"
                    cam_type = "builtin"
                else:
                    name = f"External Camera {idx} (Index {cid})"
                    cam_type = "external"

            detected.append({
                "id": cid,
                "index": idx,
                "name": name,
                "type": cam_type,
                "is_active": (cid == self._active_camera_id)
            })

        # 3. Add any registered custom / IP cameras
        for cid, cam_data in self._custom_cameras.items():
            if not any(d["id"] == cid for d in detected):
                detected.append({
                    **cam_data,
                    "is_active": (cid == self._active_camera_id)
                })

        return detected

    def register_browser_devices(self, devices: List[Dict[str, Any]]):
        """
        Stores human-readable camera labels detected by the client's browser (via MediaDevices API).
        """
        for idx, dev in enumerate(devices):
            label = dev.get("label", "").strip()
            cid = str(dev.get("index", idx))
            if label:
                self._browser_devices[cid] = label

    def get_active_camera(self) -> Dict[str, Any]:
        """
        Returns the currently active camera configuration.
        """
        cams = self.get_system_cameras()
        active = next((c for c in cams if c["id"] == self._active_camera_id), None)
        if not active:
            active = {
                "id": self._active_camera_id,
                "index": int(self._active_camera_id) if self._active_camera_id.isdigit() else None,
                "name": f"Camera {self._active_camera_id}",
                "type": "external" if self._active_camera_id != "0" else "builtin",
                "is_active": True
            }
        return active

    def set_active_camera(self, camera_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Sets the active camera ID and stores optional metadata.
        """
        self._active_camera_id = str(camera_id).strip()
        if name and self._active_camera_id not in self._custom_cameras:
            self._custom_cameras[self._active_camera_id] = {
                "id": self._active_camera_id,
                "index": int(self._active_camera_id) if self._active_camera_id.isdigit() else None,
                "name": name,
                "type": "external" if self._active_camera_id != "0" else "builtin"
            }
        return self.get_active_camera()

camera_service = CameraService()
