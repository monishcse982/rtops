from datetime import datetime
import os
from pathlib import Path

from locust import events

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_RUN_ROOT = PROJECT_ROOT / "reports" / "locust" / "local"


def _build_run_dir(report_run_root: Path) -> Path:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    return report_run_root / run_id


@events.init_command_line_parser.add_listener
def configure_local_report_defaults(parser):
    report_run_root = Path(os.getenv("LOCUST_REPORT_RUN_ROOT", str(DEFAULT_REPORT_RUN_ROOT)))
    if not report_run_root.is_absolute():
        report_run_root = PROJECT_ROOT / report_run_root

    run_dir = _build_run_dir(report_run_root)
    parser.set_defaults(
        html_file=str(run_dir / "report.html"),
        csv_prefix=str(run_dir / "stats"),
        json_file=str(run_dir / "stats"),
    )
    parser.add_argument(
        "--ramp-up-users",
        type=int,
        env_var="LOCUST_RAMP_UP_USERS",
        default=30,
        help="Target user count at the end of the ramp-up phase.",
    )
    parser.add_argument(
        "--ramp-up-duration",
        type=int,
        env_var="LOCUST_RAMP_UP_DURATION",
        default=60,
        help="Ramp-up duration in seconds.",
    )
    parser.add_argument(
        "--sustain-users",
        type=int,
        env_var="LOCUST_SUSTAIN_USERS",
        default=30,
        help="Target user count during the sustain phase.",
    )
    parser.add_argument(
        "--sustain-duration",
        type=int,
        env_var="LOCUST_SUSTAIN_DURATION",
        default=120,
        help="Sustain duration in seconds.",
    )
    parser.add_argument(
        "--ramp-down-users",
        type=int,
        env_var="LOCUST_RAMP_DOWN_USERS",
        default=0,
        help="Target user count at the end of the ramp-down phase.",
    )
    parser.add_argument(
        "--ramp-down-duration",
        type=int,
        env_var="LOCUST_RAMP_DOWN_DURATION",
        default=60,
        help="Ramp-down duration in seconds.",
    )


@events.init.add_listener
def prepare_report_paths(environment, **_kwargs):
    options = environment.parsed_options
    if options is None:
        return

    html_file = getattr(options, "html_file", None)
    csv_prefix = getattr(options, "csv_prefix", None)
    json_file = getattr(options, "json_file", None)
    if not html_file and not csv_prefix and not json_file:
        return

    run_dir = Path(html_file).parent if html_file else Path(csv_prefix).parent
    run_dir.mkdir(parents=True, exist_ok=True)
    environment.report_run_dir = run_dir


@events.test_start.add_listener
def print_report_paths(environment, **_kwargs):
    run_dir = getattr(environment, "report_run_dir", None)
    if not run_dir:
        return

    print(f"Locust report run directory: {run_dir}")
    print(f"Locust HTML report: {environment.parsed_options.html_file}")
    print(f"Locust CSV prefix: {environment.parsed_options.csv_prefix}")
    print(f"Locust JSON report: {environment.parsed_options.json_file}.json")
