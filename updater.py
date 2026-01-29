# IMPORTS -------------------------------------------------------------------- #

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# CONFIG LOADING ------------------------------------------------------------- #


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()

# Derived paths from config
PATHS = CONFIG["paths"]
TEMPLATES = CONFIG["templates"]
DATASHOP = CONFIG["datashop"]
GITHUB = CONFIG["github"]
DISPLAY = CONFIG["display"]
METADATA_KEYS = CONFIG["metadata_keys"]

# Build paths using pathlib
PATH_METADATA = Path(PATHS["metadata_json"])
TEMPLATE_FOLDER = Path(PATHS["templates"])
TEMP_PREFIX = Path(PATHS["work_prefix"])
REPO_R_MARKDOWN_OUTPUT = PATHS["r_markdown_output"]
REPO_PYTHON_OUTPUT = PATHS["python_output"]

BASELINK_DATASHOP = DATASHOP["base_link"]
SHOP_METADATA_LINK = DATASHOP["metadata_link"]

PROVIDER = DISPLAY["provider"]
TITLE_MAX_CHARS = DISPLAY["title_max_chars"]

GITHUB_ACCOUNT = GITHUB["account"]
REPO_NAME = GITHUB["repo_name"]
REPO_BRANCH = GITHUB["branch"]

KEYS_DATASET: list[str] = METADATA_KEYS["dataset"]
KEYS_DISTRIBUTION: list[str] = METADATA_KEYS["distribution"]


# HELPER FUNCTIONS ----------------------------------------------------------- #


def get_identifier_prefix(identifier: str) -> str:
    """Extract numeric prefix from identifier (e.g., '123@abc' -> '123')."""
    return identifier.split("@")[0]


def get_today_date() -> str:
    """Return current date as YYYY-MM-DD string."""
    return datetime.today().strftime("%Y-%m-%d")


def get_today_datetime() -> str:
    """Return current datetime as YYYY-MM-DD HH:MM:SS string."""
    return datetime.today().strftime("%Y-%m-%d %H:%M:%S")


# FUNCTIONS ------------------------------------------------------------------ #


def get_current_json() -> pd.DataFrame:
    """Request metadata catalogue from data shop.

    Returns:
        DataFrame containing dataset metadata.

    Raises:
        requests.HTTPError: If the HTTP request fails.
    """
    logger.info("Fetching metadata from %s", SHOP_METADATA_LINK)
    res = requests.get(SHOP_METADATA_LINK, timeout=30)
    res.raise_for_status()
    data = res.json()
    return pd.DataFrame(data["dataset"])


def has_csv_distribution(dists: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Filter distributions to keep only CSV entries.

    Args:
        dists: List of distribution dictionaries.

    Returns:
        List of CSV distributions, or None if none found.
    """
    csv_dists = [x for x in dists if "CSV" in x.get("format", "")]
    return csv_dists or None


def filter_csv(all_data: pd.DataFrame) -> pd.DataFrame:
    """Filter DataFrame to keep only datasets with CSV distributions.

    Args:
        all_data: DataFrame with distribution column.

    Returns:
        Filtered DataFrame with only CSV distributions.
    """
    data = all_data.copy()
    data["distribution"] = data["distribution"].apply(has_csv_distribution)
    data = data.dropna(subset=["distribution"])
    data = data.reset_index(drop=True)
    return data


def sort_data(data: pd.DataFrame) -> pd.DataFrame:
    """Sort DataFrame by integer prefix of identifier.

    Args:
        data: DataFrame with identifier column.

    Returns:
        Sorted DataFrame.
    """
    data = data.copy()
    data["id_short"] = data["identifier"].str.split("@").str[0].astype(int)
    data = data.sort_values("id_short")
    data = data.reset_index(drop=True)
    return data


def prepare_data_for_codebooks(data: pd.DataFrame) -> pd.DataFrame:
    """Prepare metadata from catalogue to create code files.

    Args:
        data: DataFrame with dataset metadata.

    Returns:
        DataFrame with additional columns for code generation.
    """
    data = data.copy()
    data["metadata"] = None
    data["contact"] = None
    data["distributions"] = None
    data["distribution_links"] = None

    logger.info("Preparing data for %d datasets", len(data))
    for idx in tqdm(data.index, desc="Preparing codebooks"):
        # Build metadata string
        md = [f"- **{k.capitalize()}** `{data.loc[idx, k]}`\n" for k in KEYS_DATASET]
        data.loc[idx, "metadata"] = "".join(md)

        # Extract contact info safely
        contact_point = data.loc[idx, "contactPoint"]
        if contact_point and len(contact_point) > 0:
            contact_data = [x for x in contact_point[0].values() if x is not None]
            data.loc[idx, "contact"] = " | ".join(contact_data)
        else:
            data.loc[idx, "contact"] = "N/A"

        tmp_dists = []
        tmp_links = []
        for dist in data.loc[idx, "distribution"]:
            # Remove line breaks from description since these break comment blocks
            description = dist.get("description")
            if description is not None:
                dist["description"] = re.sub(r"\n+", " ", description)
            # Use .get() to avoid KeyError on missing keys
            md = [
                f"# {k.capitalize():<25}: {dist.get(k, 'N/A')}\n"
                for k in KEYS_DISTRIBUTION
            ]
            tmp_dists.append("".join(md))
            tmp_links.append(dist.get("downloadUrl", ""))

        # Use .at[] to properly add a list as value to row
        data.at[idx, "distributions"] = tmp_dists
        data.at[idx, "distribution_links"] = tmp_links

    return data


def create_python_notebooks(data: pd.DataFrame) -> None:
    """Create Jupyter Notebooks with Python starter code.

    Args:
        data: DataFrame with prepared dataset metadata.
    """
    template_path = TEMPLATE_FOLDER / TEMPLATES["python"]
    output_dir = TEMP_PREFIX / REPO_PYTHON_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)

    with template_path.open(encoding="utf-8") as f:
        py_nb_template = f.read()

    logger.info("Creating %d Python notebooks", len(data))
    for idx in tqdm(data.index, desc="Python notebooks"):
        py_nb = py_nb_template
        identifier = data.loc[idx, "identifier"]

        # Populate template with metadata (replace " with ' for JSON safety)
        py_nb = py_nb.replace("{{ PROVIDER }}", PROVIDER)
        py_nb = py_nb.replace(
            "{{ DATASET_TITLE }}", data.loc[idx, "title"].replace('"', "'")
        )
        py_nb = py_nb.replace(
            "{{ DATASET_DESCRIPTION }}",
            data.loc[idx, "description"].replace('"', "'"),
        )
        py_nb = py_nb.replace("{{ DATASET_IDENTIFIER }}", identifier)
        py_nb = py_nb.replace(
            "{{ DATASET_METADATA }}", data.loc[idx, "metadata"].replace('"', "'")
        )
        py_nb = py_nb.replace(
            "{{ DISTRIBUTION_COUNT }}", str(len(data.loc[idx, "distributions"]))
        )
        py_nb = py_nb.replace(
            "{{ DATASHOP_LINK }}",
            f"[Direct data shop link for dataset]({BASELINK_DATASHOP}{identifier})",
        )
        py_nb = py_nb.replace("{{ CONTACT }}", data.loc[idx, "contact"])

        # Parse JSON to populate distribution code cell
        # Note: strict=False allows control characters that may be in template
        py_nb_dict = json.loads(py_nb, strict=False)

        # Find the distribution placeholder cell
        dist_cell_idx = None
        for cell_idx, cell in enumerate(py_nb_dict["cells"]):
            if cell["source"] == ["{{ DISTRIBUTION }}"]:
                dist_cell_idx = cell_idx
                break

        if dist_cell_idx is None:
            logger.warning("Distribution placeholder not found for %s", identifier)
            continue

        # Build code blocks for each CSV distribution
        code_lines = []
        for id_dist, (dist, dist_link) in enumerate(
            zip(
                data.loc[idx, "distributions"],
                data.loc[idx, "distribution_links"],
                strict=True,
            )
        ):
            code = (
                f"# Distribution {id_dist}\n{dist}\ndf = get_dataset('{dist_link}')\n"
            )
            code_lines.extend(f"{line}\n" for line in code.split("\n"))

        py_nb_dict["cells"][dist_cell_idx]["source"] = "".join(code_lines)

        # Save notebook
        output_path = output_dir / f"{identifier}.ipynb"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(py_nb_dict, f)


def create_rmarkdown(data: pd.DataFrame) -> None:
    """Create R Markdown files with R starter code.

    Args:
        data: DataFrame with prepared dataset metadata.
    """
    template_path = TEMPLATE_FOLDER / TEMPLATES["rmarkdown"]
    output_dir = TEMP_PREFIX / REPO_R_MARKDOWN_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)

    with template_path.open(encoding="utf-8") as f:
        rmd_template = f.read()

    today_date = get_today_date()

    logger.info("Creating %d R Markdown files", len(data))
    for idx in tqdm(data.index, desc="R Markdown files"):
        rmd = rmd_template
        identifier = data.loc[idx, "identifier"]

        # Populate template with metadata
        rmd = rmd.replace("{{ DATASET_TITLE }}", data.loc[idx, "title"])
        rmd = rmd.replace("{{ PROVIDER }}", PROVIDER)
        rmd = rmd.replace("{{ TODAY_DATE }}", today_date)
        rmd = rmd.replace("{{ DATASET_IDENTIFIER }}", identifier)
        rmd = rmd.replace("{{ DATASET_DESCRIPTION }}", data.loc[idx, "description"])
        rmd = rmd.replace("{{ DATASET_METADATA }}", data.loc[idx, "metadata"])
        rmd = rmd.replace("{{ CONTACT }}", data.loc[idx, "contact"])
        rmd = rmd.replace(
            "{{ DISTRIBUTION_COUNT }}", str(len(data.loc[idx, "distributions"]))
        )
        rmd = rmd.replace(
            "{{ DATASHOP_LINK }}",
            f"[Direct data shop link for dataset]({BASELINK_DATASHOP}{identifier})",
        )

        # Build code blocks for all distributions
        code_blocks = [
            f"# Distribution {id_dist}\n{dist}\ndf <- read_delim('{dist_link}')\n\n"
            for id_dist, (dist, dist_link) in enumerate(
                zip(
                    data.loc[idx, "distributions"],
                    data.loc[idx, "distribution_links"],
                    strict=True,
                )
            )
        ]
        rmd = rmd.replace("{{ DISTRIBUTIONS }}", "".join(code_blocks))

        # Save to disk
        output_path = output_dir / f"{identifier}.Rmd"
        with output_path.open("w", encoding="utf-8") as f:
            f.write(rmd)


def get_header(dataset_count: int) -> str:
    """Retrieve header template and populate with date and count of data records.

    Args:
        dataset_count: Number of datasets to display.

    Returns:
        Populated header string.
    """
    template_path = TEMPLATE_FOLDER / TEMPLATES["header"]
    with template_path.open(encoding="utf-8") as f:
        header = f.read()
    header = header.replace("{{ DATASET_COUNT }}", str(dataset_count))
    header = header.replace("{{ TODAY_DATE }}", get_today_datetime())
    return header


def create_overview(data: pd.DataFrame) -> None:
    """Create README with link table.

    Args:
        data: DataFrame with prepared dataset metadata.
    """
    TEMP_PREFIX.mkdir(parents=True, exist_ok=True)

    baselink_r_gh = (
        f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}"
        f"/blob/{REPO_BRANCH}/{REPO_R_MARKDOWN_OUTPUT}"
    )
    baselink_py_gh = (
        f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}"
        f"/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}"
    )
    baselink_py_colab = (
        f"https://githubtocolab.com/{GITHUB_ACCOUNT}/{REPO_NAME}"
        f"/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}"
    )

    header = get_header(len(data))

    md_doc = [
        header,
        f"| ID | Title (abbreviated to {TITLE_MAX_CHARS} chars) "
        "| Python Colab | Python GitHub | R GitHub |\n",
        "| :-- | :-- | :-- | :-- | :-- |\n",
    ]

    logger.info("Creating overview README with %d datasets", len(data))
    for idx in tqdm(data.index, desc="Building README"):
        identifier = data.loc[idx, "identifier"]
        id_prefix = get_identifier_prefix(identifier)

        # Remove square brackets from title (breaks markdown links)
        title_clean = data.loc[idx, "title"].replace("[", " ").replace("]", " ")
        if len(title_clean) > TITLE_MAX_CHARS:
            title_clean = f"{title_clean[:TITLE_MAX_CHARS]}…"

        ds_link = f"{BASELINK_DATASHOP}{identifier}"
        r_gh_link = f"[R GitHub]({baselink_r_gh}{identifier}.Rmd)"
        py_gh_link = f"[Python GitHub]({baselink_py_gh}{identifier}.ipynb)"
        py_colab_link = (
            f"[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]"
            f"({baselink_py_colab}{identifier}.ipynb)"
        )

        md_doc.append(
            f"| {id_prefix} | [{title_clean}]({ds_link}) "
            f"| {py_colab_link} | {py_gh_link} | {r_gh_link} |\n"
        )

    output_path = TEMP_PREFIX / "README.md"
    with output_path.open("w", encoding="utf-8") as f:
        f.write("".join(md_doc))


# CREATE CODE FILES ---------------------------------------------------------- #


def main() -> None:
    """Main entry point: fetch data and generate all starter code files."""
    logger.info("Starting startercode generation")

    try:
        datasets = (
            get_current_json()
            .pipe(filter_csv)
            .pipe(sort_data)
            .pipe(prepare_data_for_codebooks)
        )

        logger.info("Found %d datasets with CSV distributions", len(datasets))

        create_python_notebooks(datasets)
        create_rmarkdown(datasets)
        create_overview(datasets)

        logger.info("Startercode generation completed successfully")

    except requests.RequestException as e:
        logger.exception("Failed to fetch metadata: %s", e)
        raise SystemExit(1) from e
    except (OSError, json.JSONDecodeError) as e:
        logger.exception("File operation or JSON parsing failed: %s", e)
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
