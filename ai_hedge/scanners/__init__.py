"""System B scanner package — Stage 1 universe screening."""

from ai_hedge.scanners.sunset_scanner import (
    Candidate,
    ScanConfig,
    ScanResult,
    run_sunset_scan,
    write_scan_outputs,
)

__all__ = [
    "Candidate",
    "ScanConfig",
    "ScanResult",
    "run_sunset_scan",
    "write_scan_outputs",
]
