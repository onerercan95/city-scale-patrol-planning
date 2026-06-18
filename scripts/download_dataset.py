from pathlib import Path
from urllib.request import urlopen


DATASET_URL = (
    "https://data.lacity.org/api/views/2nrs-mtv8/rows.csv?accessType=DOWNLOAD"
)
OUTPUT_PATH = Path("data/LA_Crime_Data_from_2020_to_2024.csv")
CHUNK_SIZE = 1024 * 1024


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = OUTPUT_PATH.with_suffix(".csv.part")

    print("Downloading the City of Los Angeles crime dataset...")
    downloaded = 0
    try:
        with urlopen(DATASET_URL) as response, temporary_path.open("wb") as output:
            while chunk := response.read(CHUNK_SIZE):
                output.write(chunk)
                downloaded += len(chunk)
                print(f"\rDownloaded {downloaded / (1024 * 1024):.1f} MB", end="")
        temporary_path.replace(OUTPUT_PATH)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    print(f"\nDataset saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
