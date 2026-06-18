from pathlib import Path


def data_directory(run_directory: Path) -> Path:
    path = Path(run_directory) / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def image_directory(run_directory: Path) -> Path:
    path = Path(run_directory) / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def html_directory(run_directory: Path) -> Path:
    path = Path(run_directory) / "html"
    path.mkdir(parents=True, exist_ok=True)
    return path


def grouped_data_directory(run_directory: Path, group: str) -> Path:
    path = data_directory(run_directory) / group
    path.mkdir(parents=True, exist_ok=True)
    return path


def grouped_image_directory(run_directory: Path, group: str) -> Path:
    path = image_directory(run_directory) / group
    path.mkdir(parents=True, exist_ok=True)
    return path
