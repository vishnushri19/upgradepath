from __future__ import annotations

from pathlib import Path

from f5upgrade.bigip_client import BigIPClient
from f5upgrade.config import load_settings
from f5upgrade.execution import (
    _get_volume_state,
    exec_reboot_to_volume_standby,
    exec_volume_ready,
    exec_wait_postboot,
)
from f5upgrade.flow import FlowOptions, UpgradeFlow
from f5upgrade.report import CheckResult, to_report, write_json, write_markdown
from f5upgrade.state_collector import StateCollector

from run_state_diff import run_collection, run_diff


def _safe_host(host: str) -> str:
    return host.replace(":", "_").replace("/", "_").replace(".", "_")


def _write_resume_report(
    output_dir: Path,
    safe_host: str,
    host: str,
    results: list[CheckResult],
) -> None:
    report = to_report(
        results,
        meta={"bigip_host": host, "mode": "resume"},
    )
    json_path = output_dir / f"upgrade_resume_report_{safe_host}.json"
    markdown_path = output_dir / f"upgrade_resume_report_{safe_host}.md"
    write_json(str(json_path), report)
    write_markdown(str(markdown_path), report)
    print(f"[+] Wrote resume report: {markdown_path}")


def _backup_set_is_complete(backups_dir: Path) -> bool:
    """Require the minimum backup artifacts before retrying Stage 2."""
    return (
        any(backups_dir.glob("*.ucs"))
        and any(backups_dir.glob("*.tar"))
        and any(backups_dir.glob("*qkview*"))
    )


def main() -> int:
    """Continue an interrupted node upgrade without repeating completed work."""
    settings = load_settings()
    safe_host = _safe_host(settings.host)
    output_dir = Path("outputs") / settings.crq_number
    snapshots_dir = output_dir / "snapshots"
    backups_dir = output_dir / "backups"
    pre_json = snapshots_dir / f"pre_state_{safe_host}.json"

    if not pre_json.exists():
        print(
            f"[-] Pre-upgrade snapshot not found: {pre_json}. "
            "Resume is blocked to preserve pre/post comparison evidence."
        )
        return 2

    client = BigIPClient(
        host=settings.host,
        username=settings.username,
        password=settings.password,
        verify_tls=settings.verify_tls,
        timeout=settings.timeout,
    )
    results: list[CheckResult] = []

    print("\n[RESUME] Inspecting the existing target volume. No upload, backup, "
          "license validation, or install command will be repeated.")
    state = _get_volume_state(client, settings.target_volume)
    if not state.found:
        if not _backup_set_is_complete(backups_dir):
            results.append(
                CheckResult(
                    id="RESUME-BACKUP-001",
                    category="Resume",
                    name="Complete pre-upgrade backup set available",
                    status="FAIL",
                    details={
                        "backups_dir": str(backups_dir),
                        "error": (
                            "Resume before installation is blocked because "
                            "the required UCS, SCF archive, and QKView "
                            "backup artifacts were not all found."
                        ),
                    },
                )
            )
            _write_resume_report(output_dir, safe_host, settings.host, results)
            return 2

        print(
            "\n[RESUME] Target volume does not exist. Retrying only Stage 2 "
            "(ISO upload, install, and reboot) with the current settings."
        )
        flow = UpgradeFlow(
            client=client,
            options=FlowOptions(
                allow_risk_accepted=True,
                fail_fast=True,
                require_standby=True,
            ),
            settings=settings,
        )
        results.extend(flow.run())
    else:
        version_text = str(client.system_version())
        if settings.target_image_contains in version_text:
            postboot = exec_wait_postboot(
                client,
                settings.target_image_contains,
                timeout_sec=30,
                interval_sec=5,
            )
            results.append(postboot)
        else:
            volume_result = exec_volume_ready(
                client,
                settings.target_volume,
                settings.target_image_contains,
            )
            results.append(volume_result)
            if volume_result.status == "PASS":
                reboot_result = exec_reboot_to_volume_standby(
                    client,
                    settings.target_volume,
                )
                results.append(reboot_result)
                if reboot_result.status == "PASS":
                    results.append(
                        exec_wait_postboot(
                            client,
                            settings.target_image_contains,
                        )
                    )

    _write_resume_report(output_dir, safe_host, settings.host, results)
    report = to_report(results, meta={"bigip_host": settings.host, "mode": "resume"})
    if report["overall_status"] != "PASS":
        print(
            f"[-] Resume stopped safely with status "
            f"{report['overall_status']}."
        )
        return 2

    collector = StateCollector(
        client,
        crq_number=settings.crq_number,
        phase="post",
    )
    post_json = run_collection(
        collector,
        settings.host,
        "post",
        output_dir,
    )
    return run_diff(pre_json, post_json, settings.host, output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
