from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field


class AssetRuntimeStatus:
    """Runtime status constants for Asset runtime."""

    UNAVAILABLE = "unavailable"
    DRY_RUN = "dry_run"
    EXTERNAL_REQUIRED = "external_required"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class AssetCapability:
    """Describes a single asset capability that can be requested."""

    name: str
    description: str
    supported: bool = True
    dry_run_only: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AssetCapability:
        return cls(**d)


@dataclass
class AssetRequest:
    """A request for asset runtime processing."""

    id: str
    mode: str
    reason: str
    user_id: str | None
    thread_id: str | None
    run_id: str | None
    requested_capability: str | None
    payload_summary: str
    source: str = "mode_router"
    dry_run: bool = True

    @classmethod
    def new(
        cls,
        mode: str = "",
        reason: str = "",
        user_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        requested_capability: str | None = None,
        payload_summary: str = "",
        source: str = "mode_router",
        dry_run: bool = True,
    ) -> AssetRequest:
        return cls(
            id=str(uuid.uuid4()),
            mode=mode,
            reason=reason,
            user_id=user_id,
            thread_id=thread_id,
            run_id=run_id,
            requested_capability=requested_capability,
            payload_summary=payload_summary,
            source=source,
            dry_run=dry_run,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AssetRequest:
        return cls(**d)


@dataclass
class AssetResult:
    """The result of an asset runtime execution attempt."""

    request_id: str
    status: str
    capability: str | None
    dry_run: bool
    message: str
    artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AssetResult:
        artifacts = d.pop("artifacts", [])
        warnings = d.pop("warnings", [])
        instance = cls(**d)
        instance.artifacts = artifacts
        instance.warnings = warnings
        return instance
