import hmac
from dataclasses import dataclass, field
from typing import Dict, List, Set

from .manifest import AppManifest


def _vtuple(v: str):
    return tuple(int(p) for p in v.split("."))


@dataclass
class KernelInfo:
    version: str
    capabilities: Set[str] = field(default_factory=set)


@dataclass
class TenantContext:
    tenant_id: str
    entitlements: Set[str] = field(default_factory=set)
    authorized_installers: Set[str] = field(default_factory=set)
    domains: Set[str] = field(default_factory=lambda: {"therapeutic"})
    installed_apps: Set[str] = field(default_factory=set)
    max_monthly_ceiling_usd: float = float("inf")


@dataclass
class PlatformContext:
    """What the provisioning service can see about the platform at install time."""
    publisher_keys: Dict[str, bytes] = field(default_factory=dict)
    kernels: Dict[str, KernelInfo] = field(default_factory=dict)
    hosting_services: Set[str] = field(default_factory=set)


def validate_install(
    manifest: AppManifest,
    signature: str,
    requested_by: str,
    tenant: TenantContext,
    platform: PlatformContext,
) -> List[str]:
    """Return a list of human-readable violations; empty means the install may proceed."""
    errors: List[str] = []

    key = platform.publisher_keys.get(manifest.publisher)
    if key is None:
        errors.append(f"unknown publisher '{manifest.publisher}'")
    elif not hmac.compare_digest(manifest.sign(key), signature):
        errors.append("publisher signature verification failed")

    if manifest.name not in tenant.entitlements:
        errors.append(f"tenant not entitled to '{manifest.name}'")
    if requested_by not in tenant.authorized_installers:
        errors.append(f"'{requested_by}' lacks tenant install authority")
    if manifest.domain not in tenant.domains:
        errors.append(f"domain '{manifest.domain}' not enabled for tenant")
    if manifest.name in tenant.installed_apps:
        errors.append(f"'{manifest.name}' already installed")

    if manifest.requires_any_of and not tenant.installed_apps.intersection(manifest.requires_any_of):
        errors.append(f"requires one of installed apps: {', '.join(manifest.requires_any_of)}")

    if manifest.spend_policy.monthly_ceiling_usd > tenant.max_monthly_ceiling_usd:
        errors.append("requested monthly ceiling exceeds tenant policy limit")

    for kname, req in manifest.kernels.items():
        info = platform.kernels.get(kname)
        if info is None:
            if req.required:
                errors.append(f"required kernel '{kname}' unavailable")
            continue
        if _vtuple(info.version) < _vtuple(req.min_version):
            errors.append(f"kernel '{kname}' {info.version} < required {req.min_version}")
        missing = set(req.capabilities) - info.capabilities
        if missing:
            errors.append(f"kernel '{kname}' missing capabilities: {', '.join(sorted(missing))}")

    for dep in manifest.hosting_dependencies:
        if dep not in platform.hosting_services:
            errors.append(f"hosting dependency '{dep}' unavailable")

    return errors
