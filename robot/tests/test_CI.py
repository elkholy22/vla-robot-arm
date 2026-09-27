import os

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_repo_layout():
    assert os.path.isdir(os.path.join(REPO_ROOT, "src"))


def test_ci_pipeline_runs():
    assert True