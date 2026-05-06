import sys
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
import shutil
import subprocess

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from TestConfig import TestConfig
from app.models.outbox_event_model import OutboxEvent

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORTS_ROOT = PROJECT_ROOT / "reports"
ALLURE_RESULTS_ROOT = REPORTS_ROOT / "allure-results"
ALLURE_REPORT_ROOT = REPORTS_ROOT / "allure-report"
CURRENT_ALLURE_RESULTS_DIR = ALLURE_RESULTS_ROOT / "current"


def pytest_configure(config):
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    final_results_dir = ALLURE_RESULTS_ROOT / run_id
    final_report_dir = ALLURE_REPORT_ROOT / run_id

    config._allure_run_id = run_id
    config._allure_current_results_dir = CURRENT_ALLURE_RESULTS_DIR
    config._allure_final_results_dir = final_results_dir
    config._allure_final_report_dir = final_report_dir
    config._allure_html_index = final_report_dir / "index.html"
    config._allure_generation_error = None


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if config.option.collectonly:
        return

    current_results_dir = config._allure_current_results_dir
    final_results_dir = config._allure_final_results_dir
    final_report_dir = config._allure_final_report_dir

    if not current_results_dir.exists():
        return

    final_results_dir.parent.mkdir(parents=True, exist_ok=True)
    final_report_dir.parent.mkdir(parents=True, exist_ok=True)

    if final_results_dir.exists():
        shutil.rmtree(final_results_dir)
    shutil.move(str(current_results_dir), str(final_results_dir))

    if final_report_dir.exists():
        shutil.rmtree(final_report_dir)

    try:
        subprocess.run(
            [
                "allure",
                "generate",
                str(final_results_dir),
                "-o",
                str(final_report_dir),
                "--clean",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        config._allure_generation_error = exc


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if config.option.collectonly:
        return

    terminalreporter.write_sep("-", "Allure report artifacts")
    terminalreporter.write_line(f"Allure results folder: {config._allure_final_results_dir}")
    if config._allure_generation_error is None:
        terminalreporter.write_line(f"Allure HTML report folder: {config._allure_final_report_dir}")
        terminalreporter.write_line(f"Allure HTML index: {config._allure_html_index}")
    else:
        terminalreporter.write_line("Allure HTML report generation failed.")
        terminalreporter.write_line(
            f"Results are still available at: {config._allure_final_results_dir}"
        )
        terminalreporter.write_line(f"Generation error: {config._allure_generation_error}")


@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    return TestConfig.load_config()


@pytest.fixture(scope="session")
def db_engine(test_config: TestConfig):
    engine = create_engine(test_config.database_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    session_local = sessionmaker(bind=db_engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_order_test_state(db_session):
    db_session.query(OutboxEvent).delete()
    db_session.commit()
