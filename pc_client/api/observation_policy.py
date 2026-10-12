"""Presentation read periods, independent of actuator timing and safety reads."""

INTERVALS = {
    "state": 2.0,
    "sysinfo": 2.0,
    "healthz": 5.0,
    "vision_snap_info": 2.0,
    "vision_obstacle": 2.0,
    "app_metrics": 10.0,
    "bus_health": 10.0,
}


def reuse_period(key):
    if key in {"camera_resource", "lcd_resource"} or key.startswith("resource:"):
        return 4.0
    if key == "catalog":
        return 5.0
    return 0.0
