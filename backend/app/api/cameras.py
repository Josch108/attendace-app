from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, status

from app.services.camera_service import camera_service
from app.websockets.connection_manager import ws_manager

router = APIRouter(prefix="/cameras", tags=["Cameras"])

class CameraItem(BaseModel):
    id: str
    index: Optional[int] = None
    name: str
    type: str = "builtin"
    is_active: bool = False

class CameraListResponse(BaseModel):
    cameras: List[CameraItem]
    active_camera: str

class SetActiveCameraRequest(BaseModel):
    camera_id: str = Field(..., description="Camera ID or numeric device index (e.g. '0', '1')")
    name: Optional[str] = Field(None, description="Optional friendly name of the camera")

class BrowserDeviceItem(BaseModel):
    deviceId: Optional[str] = None
    label: str
    index: Optional[int] = 0

class RegisterBrowserDevicesRequest(BaseModel):
    devices: List[BrowserDeviceItem]

@router.get("", response_model=CameraListResponse)
def list_cameras():
    """
    Returns the list of available cameras (built-in, external USB devices, etc.)
    and indicates which one is currently selected as active.
    """
    cameras = camera_service.get_system_cameras()
    active = camera_service.get_active_camera()
    return CameraListResponse(
        cameras=[CameraItem(**c) for c in cameras],
        active_camera=str(active["id"])
    )

@router.get("/active", response_model=CameraItem)
def get_active_camera():
    """
    Returns the currently active camera source.
    """
    active = camera_service.get_active_camera()
    return CameraItem(**active)

@router.post("/active", response_model=CameraItem, status_code=status.HTTP_200_OK)
def set_active_camera(req: SetActiveCameraRequest):
    """
    Changes the active camera source.
    Broadcasts the change via WebSockets so the live dashboard and vision pipeline can switch in real time.
    """
    updated = camera_service.set_active_camera(camera_id=req.camera_id, name=req.name)

    # Broadcast notification to all active dashboards and clients
    ws_manager.broadcast_all_sync({
        "type": "camera_changed",
        "data": {
            "camera_id": updated["id"],
            "camera_name": updated["name"],
            "type": updated["type"]
        }
    })

    return CameraItem(**updated)

@router.post("/register-browser", status_code=status.HTTP_200_OK)
def register_browser_devices(req: RegisterBrowserDevicesRequest):
    """
    Accepts video devices detected by the browser (navigator.mediaDevices) to provide
    exact hardware device labels for connected cameras.
    """
    dev_dicts = [{"label": d.label, "index": d.index} for d in req.devices]
    camera_service.register_browser_devices(dev_dicts)
    return {"status": "ok", "registered_count": len(dev_dicts)}
