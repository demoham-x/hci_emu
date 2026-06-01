from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path


APP_DIR_NAME = "HCIEMU"
LOCAL_CONFIG_DIR_NAME = ".hciemu_configs"
PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_CONFIG_DIR = PACKAGE_ROOT / "configs"
PACKAGE_RESOURCE_DIR = PACKAGE_ROOT / "resources"
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PACKAGE_ROOT))
BUNDLE_CONFIG_DIR = BUNDLE_ROOT / "configs"
BUNDLE_RESOURCE_DIR = BUNDLE_ROOT / "resources"
REPO_ROOT = PACKAGE_ROOT.parent.parent
REPO_CONFIG_DIR = REPO_ROOT / "configs"
REPO_RESOURCE_DIR = REPO_ROOT / "resources"
REPO_LOG_DIR = REPO_ROOT / "logs"


def is_test_mode() -> bool:
    return "test" in {arg.strip().lower() for arg in sys.argv[1:]}


def is_repo_checkout() -> bool:
    if is_test_mode():
        return REPO_CONFIG_DIR.exists() and REPO_RESOURCE_DIR.exists()

    return (
        (REPO_ROOT / "pyproject.toml").exists()
        and REPO_CONFIG_DIR.exists()
        and REPO_RESOURCE_DIR.exists()
    )


def is_frozen_executable() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_runtime_dir() -> Path:
    if is_frozen_executable():
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def get_user_data_dir() -> Path:
    if is_frozen_executable():
        return get_runtime_dir() / LOCAL_CONFIG_DIR_NAME

    if os.name == "nt":
        base_dir = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if base_dir:
            return Path(base_dir) / APP_DIR_NAME

    base_dir = os.getenv("XDG_CONFIG_HOME")
    if base_dir:
        return Path(base_dir) / APP_DIR_NAME.lower()

    return Path.home() / ".config" / APP_DIR_NAME.lower()


def get_user_config_dir() -> Path:
    if is_frozen_executable():
        return get_user_data_dir()
    return get_user_data_dir() / "configs"


def get_user_log_dir() -> Path:
    return get_user_data_dir() / "logs"


def _copy_default_file(source_path: Path, target_path: Path) -> None:
    if not source_path.exists() or target_path.exists():
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


def ensure_user_files() -> None:
    if is_repo_checkout():
        REPO_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return

    get_user_config_dir().mkdir(parents=True, exist_ok=True)
    get_user_log_dir().mkdir(parents=True, exist_ok=True)


def get_user_config_path(name: str) -> Path:
    if is_repo_checkout():
        return REPO_CONFIG_DIR / name

    ensure_user_files()
    target_path = get_user_config_dir() / name
    source_path = BUNDLE_CONFIG_DIR / name if is_frozen_executable() else PACKAGE_CONFIG_DIR / name
    _copy_default_file(source_path, target_path)
    return target_path


def get_resource_dir() -> Path:
    if is_repo_checkout():
        return REPO_RESOURCE_DIR

    if is_frozen_executable() and BUNDLE_RESOURCE_DIR.exists():
        return BUNDLE_RESOURCE_DIR

    return PACKAGE_RESOURCE_DIR


def get_log_dir() -> Path:
    ensure_user_files()
    if is_repo_checkout():
        return REPO_LOG_DIR

    return get_user_log_dir()


def get_capture_log_path() -> Path:
    return get_log_dir() / "hci_capture.log"


def get_debug_log_path() -> Path:
    return get_log_dir() / "debug.log"
