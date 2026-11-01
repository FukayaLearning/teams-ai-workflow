"""設定ファイルの読み込みとOneDriveキューフォルダパスの解決モジュール."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import yaml


@dataclass
class LMStudioConfig:
    base_url: str = "http://127.0.0.1:1234/v1"
    model: str = "qwen2.5-7b-instruct"
    timeout_seconds: int = 60
    max_retries: int = 2
    temperature: float = 0.2


@dataclass
class QueueDirectories:
    root: Path
    incoming: Path
    processed: Path
    failed: Path


@dataclass
class QueueConfig:
    base_dir: str = "auto"
    queue_folder_name: str = "TeamsQueue"
    poll_interval_seconds: int = 5


@dataclass
class DatabaseConfig:
    path: str = "teams_workflow.db"


@dataclass
class ActionsConfig:
    enable_toast_notification: bool = True
    enable_auto_clipboard: bool = True


@dataclass
class UserProfile:
    name: str = ""
    role: str = ""
    self_names: list[str] = field(default_factory=list)
    self_emails: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    ignore_topics: list[str] = field(default_factory=list)

    def is_self_sender(self, sender_name: str, sender_email: str | None = None) -> bool:
        """送信者がユーザー自身かどうかを判定する."""
        normalized_name = sender_name.strip().lower()
        candidate_names = {n.strip().lower() for n in self.self_names if n.strip()}
        if self.name.strip():
            candidate_names.add(self.name.strip().lower())

        if normalized_name and normalized_name in candidate_names:
            return True

        if sender_email:
            normalized_email = sender_email.strip().lower()
            candidate_emails = {e.strip().lower() for e in self.self_emails if e.strip()}
            if normalized_email and normalized_email in candidate_emails:
                return True

        return False


@dataclass
class AppSettings:
    lm_studio: LMStudioConfig = field(default_factory=LMStudioConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    actions: ActionsConfig = field(default_factory=ActionsConfig)
    user_profile: UserProfile = field(default_factory=UserProfile)


def resolve_queue_directories(
    queue_config: QueueConfig,
    environ: Mapping[str, str] | None = None,
    fallback_root: Path | None = None,
    ensure_exists: bool = True,
) -> QueueDirectories:
    """OneDrive同期フォルダまたは明示パスのキューディレクトリを解決し、必要に応じて作成する."""
    env = environ if environ is not None else os.environ
    base_dir_setting = (queue_config.base_dir or "auto").strip()
    folder_name = queue_config.queue_folder_name or "TeamsQueue"

    queue_root: Path | None = None

    if base_dir_setting.lower() != "auto":
        expanded = os.path.expandvars(os.path.expanduser(base_dir_setting))
        candidate = Path(expanded)
        if candidate.name == folder_name:
            queue_root = candidate
        else:
            queue_root = candidate / folder_name
    else:
        for env_key in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive"):
            env_val = env.get(env_key, "").strip()
            if env_val:
                queue_root = Path(env_val) / folder_name
                break

        if queue_root is None:
            user_profile_dir = env.get("USERPROFILE", "").strip()
            home_dir = Path(user_profile_dir) if user_profile_dir else Path.home()
            if home_dir.exists():
                onedrive_dirs = sorted(home_dir.glob("OneDrive - *"))
                if onedrive_dirs:
                    queue_root = onedrive_dirs[0] / folder_name

        if queue_root is None:
            default_base = fallback_root if fallback_root is not None else Path.cwd() / "data"
            queue_root = default_base / folder_name

    incoming_dir = queue_root / "incoming"
    processed_dir = queue_root / "processed"
    failed_dir = queue_root / "failed"

    if ensure_exists:
        incoming_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)
        failed_dir.mkdir(parents=True, exist_ok=True)

    return QueueDirectories(
        root=queue_root,
        incoming=incoming_dir,
        processed=processed_dir,
        failed=failed_dir,
    )


def load_settings(
    settings_path: str | Path = "config/settings.yaml",
    user_profile_path: str | Path = "config/user_profile.yaml",
) -> AppSettings:
    """YAMLファイルからアプリケーション設定とユーザープロファイルを読み込む."""
    settings_file = Path(settings_path)
    profile_file = Path(user_profile_path)

    raw_settings: dict = {}
    if settings_file.exists():
        with settings_file.open("r", encoding="utf-8") as f:
            raw_settings = yaml.safe_load(f) or {}

    raw_profile: dict = {}
    if profile_file.exists():
        with profile_file.open("r", encoding="utf-8") as f:
            raw_profile = yaml.safe_load(f) or {}

    lm_data = raw_settings.get("lm_studio", {}) or {}
    queue_data = raw_settings.get("queue", {}) or {}
    db_data = raw_settings.get("database", {}) or {}
    actions_data = raw_settings.get("actions", {}) or {}

    user_data = raw_profile.get("user", {}) or {}

    lm_config = LMStudioConfig(
        base_url=str(lm_data.get("base_url", "http://127.0.0.1:1234/v1")),
        model=str(lm_data.get("model", "qwen2.5-7b-instruct")),
        timeout_seconds=int(lm_data.get("timeout_seconds", 60)),
        max_retries=int(lm_data.get("max_retries", 2)),
        temperature=float(lm_data.get("temperature", 0.2)),
    )

    queue_config = QueueConfig(
        base_dir=str(queue_data.get("base_dir", "auto")),
        queue_folder_name=str(queue_data.get("queue_folder_name", "TeamsQueue")),
        poll_interval_seconds=int(queue_data.get("poll_interval_seconds", 5)),
    )

    db_config = DatabaseConfig(
        path=str(db_data.get("path", "teams_workflow.db")),
    )

    actions_config = ActionsConfig(
        enable_toast_notification=bool(actions_data.get("enable_toast_notification", True)),
        enable_auto_clipboard=bool(actions_data.get("enable_auto_clipboard", True)),
    )

    profile = UserProfile(
        name=str(user_data.get("name", "")),
        role=str(user_data.get("role", "")),
        self_names=list(user_data.get("self_names", []) or []),
        self_emails=list(user_data.get("self_emails", []) or []),
        responsibilities=list(raw_profile.get("responsibilities", []) or []),
        keywords=list(raw_profile.get("keywords", []) or []),
        ignore_topics=list(raw_profile.get("ignore_topics", []) or []),
    )

    return AppSettings(
        lm_studio=lm_config,
        queue=queue_config,
        database=db_config,
        actions=actions_config,
        user_profile=profile,
    )

