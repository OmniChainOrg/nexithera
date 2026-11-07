import hashlib
import hmac
import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Tier(str, Enum):
    standard = "standard"
    enterprise = "enterprise"
    pro_addon = "pro_addon"


class Enforcement(str, Enum):
    hard_stop = "hard_stop"
    reservation = "reservation"
    controlled_overage = "controlled_overage"


class KernelRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: bool = True
    min_version: str
    capabilities: List[str] = Field(default_factory=list)


class SpendPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monthly_ceiling_usd: float = Field(gt=0)
    enforcement: Enforcement
    overage_limit_pct: Optional[float] = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def _overage_consistent(self):
        if self.enforcement == Enforcement.controlled_overage and self.overage_limit_pct is None:
            raise ValueError("controlled_overage requires overage_limit_pct")
        if self.enforcement != Enforcement.controlled_overage and self.overage_limit_pct is not None:
            raise ValueError("overage_limit_pct only valid with controlled_overage")
        return self


class AppManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    display_name: str
    tier: Tier
    publisher: str
    domain: str
    description: str = ""
    kernels: Dict[str, KernelRequirement]
    requires_any_of: List[str] = Field(default_factory=list)
    hosting_dependencies: List[str] = Field(default_factory=list)
    spend_policy: SpendPolicy

    @model_validator(mode="after")
    def _needs_epistemicos(self):
        ep = self.kernels.get("epistemicos")
        if ep is None or not ep.required:
            raise ValueError("every app requires epistemicos (governance kernel)")
        return self

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def sign(self, key: bytes) -> str:
        return hmac.new(key, self.canonical_bytes(), hashlib.sha256).hexdigest()


def load_manifest(path: Path) -> AppManifest:
    return AppManifest.model_validate(yaml.safe_load(Path(path).read_text()))


def load_manifests(directory: Path) -> Dict[str, AppManifest]:
    return {m.name: m for m in (load_manifest(p) for p in sorted(Path(directory).glob("*.yaml")))}
