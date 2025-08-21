"""Debug and logging utilities for E-ink Composer."""

import logging
import os
import sys
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, Optional


# Load debug configuration from file or environment
def load_debug_config():
    """Load debug configuration from file or environment variables."""
    config = {
        "EINK_COMPOSER_DEBUG": "false",
        "EINK_COMPOSER_LOG_LEVEL": "INFO",
        "EINK_COMPOSER_LOG_FILE": "/tmp/eink_composer/debug.log",
    }

    # Try to load from config file
    config_paths = [
        Path(__file__).parent.parent / "debug.conf",
        Path("/opt/distiller-cm5-sdk/eink_composer_debug.conf"),
        Path("/etc/eink_composer/debug.conf"),
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            if key in config:
                                config[key] = value
                break
            except Exception:
                pass

    # Environment variables override config file
    for key in config:
        env_value = os.environ.get(key)
        if env_value is not None:
            config[key] = env_value

    return config


# Load configuration
config = load_debug_config()
DEBUG_MODE = config["EINK_COMPOSER_DEBUG"].lower() == "true"
LOG_LEVEL = config["EINK_COMPOSER_LOG_LEVEL"]
LOG_FILE = config["EINK_COMPOSER_LOG_FILE"]

# Create log directory if needed
log_dir = Path(LOG_FILE).parent
log_dir.mkdir(mode=0o777, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(sys.stdout) if DEBUG_MODE else logging.NullHandler(),
    ],
)

# Create module logger
logger = logging.getLogger("eink_composer")


class DebugManager:
    """Manages debug state and provides debug utilities."""

    def __init__(self):
        """Initialize debug manager."""
        self.debug_mode = DEBUG_MODE
        self.performance_stats: dict[str, list] = {}
        self.operation_count = 0
        self.start_time = time.time()

    def is_enabled(self) -> bool:
        """Check if debug mode is enabled."""
        return self.debug_mode

    def toggle_debug(self, enabled: bool | None = None) -> bool:
        """Toggle debug mode on/off."""
        if enabled is not None:
            self.debug_mode = enabled
        else:
            self.debug_mode = not self.debug_mode

        # Update logger level
        new_level = logging.DEBUG if self.debug_mode else logging.INFO
        logger.setLevel(new_level)
        logger.info(f"Debug mode {'enabled' if self.debug_mode else 'disabled'}")

        return self.debug_mode

    def log_operation(self, operation: str, details: dict[str, Any]):
        """Log an operation with details."""
        self.operation_count += 1
        logger.debug(f"Operation #{self.operation_count}: {operation}")
        for key, value in details.items():
            logger.debug(f"  {key}: {value}")

    def log_error(self, operation: str, error: Exception, context: dict[str, Any] | None = None):
        """Log an error with context."""
        logger.error(f"Error in {operation}: {str(error)}")
        if context:
            for key, value in context.items():
                logger.error(f"  Context - {key}: {value}")
        if self.debug_mode:
            import traceback

            logger.debug(f"Stack trace:\n{traceback.format_exc()}")

    def log_performance(self, operation: str, duration: float):
        """Log performance metrics."""
        if operation not in self.performance_stats:
            self.performance_stats[operation] = []
        self.performance_stats[operation].append(duration)

        if self.debug_mode:
            avg_time = sum(self.performance_stats[operation]) / len(
                self.performance_stats[operation]
            )
            logger.debug(f"Performance - {operation}: {duration:.3f}s (avg: {avg_time:.3f}s)")

    def get_stats(self) -> dict[str, Any]:
        """Get debug statistics."""
        uptime = time.time() - self.start_time
        stats = {
            "debug_mode": self.debug_mode,
            "log_level": LOG_LEVEL,
            "log_file": LOG_FILE,
            "uptime_seconds": round(uptime, 2),
            "operation_count": self.operation_count,
            "performance_stats": {},
        }

        for op, times in self.performance_stats.items():
            if times:
                stats["performance_stats"][op] = {
                    "count": len(times),
                    "total": round(sum(times), 3),
                    "average": round(sum(times) / len(times), 3),
                    "min": round(min(times), 3),
                    "max": round(max(times), 3),
                }

        return stats

    def dump_state(self, state: dict[str, Any], label: str = "State Dump"):
        """Dump current state for debugging."""
        logger.debug(f"=== {label} ===")
        self._dump_dict(state, indent=0)
        logger.debug(f"=== End {label} ===")

    def _dump_dict(self, obj: Any, indent: int = 0):
        """Recursively dump dictionary contents."""
        prefix = "  " * indent
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, dict | list):
                    logger.debug(f"{prefix}{key}:")
                    self._dump_dict(value, indent + 1)
                else:
                    logger.debug(f"{prefix}{key}: {value}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, dict | list):
                    logger.debug(f"{prefix}[{i}]:")
                    self._dump_dict(item, indent + 1)
                else:
                    logger.debug(f"{prefix}[{i}]: {item}")
        else:
            logger.debug(f"{prefix}{obj}")


# Global debug manager instance
debug_manager = DebugManager()


def timed_operation(operation_name: str):
    """Decorator to time operations."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                debug_manager.log_performance(operation_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                debug_manager.log_error(operation_name, e, {"duration": duration})
                raise

        return wrapper

    return decorator


def log_call(func: Callable):
    """Decorator to log function calls with arguments."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if debug_manager.is_enabled():
            func_name = f"{func.__module__}.{func.__name__}"
            debug_manager.log_operation(
                f"Calling {func_name}", {"args": str(args)[:200], "kwargs": str(kwargs)[:200]}
            )
        return func(*args, **kwargs)

    return wrapper


# Logging shortcuts
def debug(msg: str, **kwargs):
    """Log debug message."""
    logger.debug(msg, **kwargs)


def info(msg: str, **kwargs):
    """Log info message."""
    logger.info(msg, **kwargs)


def warning(msg: str, **kwargs):
    """Log warning message."""
    logger.warning(msg, **kwargs)


def error(msg: str, **kwargs):
    """Log error message."""
    logger.error(msg, **kwargs)
