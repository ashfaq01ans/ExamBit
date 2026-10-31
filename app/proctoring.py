# Shared proctoring settings.
MAX_VIOLATIONS = 10                 # the exam is submitted automatically at this many
SNAPSHOT_INTERVAL_SECONDS = 30      # webcam snapshot every 30 seconds
MAX_SNAPSHOTS_PER_ATTEMPT = 400     # protects database storage
MAX_SNAPSHOT_BYTES = 200_000        # one snapshot is normally 10-25 KB

VIOLATION_LABELS = {
    "tab_switch": "Switched tab or window",
    "fullscreen_exit": "Left fullscreen",
    "screen_share_stopped": "Stopped screen sharing",
    "right_click": "Right-clicked",
    "camera_off": "Camera turned off",
}
