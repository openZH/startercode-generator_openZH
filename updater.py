# IMPORTS -------------------------------------------------------------------- #

import copy
import json
import re
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

# import warnings
# warnings.simplefilter(action='ignore', category=FutureWarning)


# CONSTANTS ------------------------------------------------------------------ #

PATH_METADATA = "_metadata_json/"
BASELINK_DATASHOP = "https://www.zh.ch/de/politik-staat/opendata.html#/datasets/"

PROVIDER = "Canton Zurich"
SHOP_METADATA_LINK = "https://www.web.statistik.zh.ch/ogd/daten/zhweb.json"
SHOP_ABBR = "ktzh"

GITHUB_ACCOUNT = "openZH"
REPO_NAME = "starter-code-openZH"
REPO_BRANCH = "main"
REPO_R_MARKDOWN_OUTPUT = "01_r-markdown/"
REPO_PYTHON_OUTPUT = "02_python/"
TEMP_PREFIX = "_work/"

TEMPLATE_FOLDER = "_templates/"
TEMPLATE_HEADER = "template_header.md"
TEMPLATE_PYTHON = "template_python.ipynb"
TEMPLATE_RMARKDOWN = "template_rmarkdown.Rmd"

TODAY_DATE = datetime.today().strftime('%Y-%m-%d')
TODAY_DATETIME = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

# max length of dataset title in markdown table
TITLE_MAX_CHARS = 200

# select metadata features that are going to be displayed in starter code files
KEYS_DATASET = ['issued', 'modified', 'startDate', 'endDate',
                'theme', 'keyword', 'publisher', 'landingPage']

KEYS_DISTRIBUTION = ['ktzhDistId', 'title', "description",
                     'issued', 'modified', "rights"]


# FUNCTIONS ------------------------------------------------------------------ #

def get_current_json():
    """Request metadata catalogue from data shop"""
    res = requests.get(SHOP_METADATA_LINK)
    # # save with date to allow for later error and change analysis
    # with open(f"{PATH_METADATA}{TODAY_DATE}.json", "wb") as file:
    #     file.write(res.content)
    data = json.loads(res.text)
    data = pd.DataFrame(data['dataset'])
    return data


def has_csv_distribution(dists):
    """Iterate over distributions and keep only CSV entries"""
    csv_dists = [x for x in dists if "CSV" in x.get("format", "")]
    return csv_dists or np.nan


def filter_csv(all_data):
    """Filter out CSV distributions"""
    data = copy.deepcopy(all_data)
    data.distribution = data.distribution.apply(has_csv_distribution)
    data.dropna(subset=["distribution"], inplace=True)
    data.reset_index(drop=True, inplace=True)
    return data


def sort_data(data):
    """Sort by integer prefix of identifier"""
    data["id_short"] = data.identifier.apply(
        lambda x: x.split("@")[0]).astype(int)
    data.sort_values("id_short", inplace=True)
    data.reset_index(drop=True, inplace=True)
    return data


def prepare_data_for_codebooks(data):
    """Prepare metadata from catalogue in order to create code files"""
    data["metadata"] = None
    data["contact"] = None
    data["distributions"] = None
    data["distribution_links"] = None

    # iterate over all datasets and compose refined data for markdown and code cells
    for idx in tqdm(data.index):
        md = [
            f"- **{k.capitalize()}** `{data.loc[idx, k]}`\n" for k in KEYS_DATASET]
        data.loc[idx, "metadata"] = "".join(md)
        contact_data = data.loc[idx, "contactPoint"][0].values()
        contact_data = [x for x in contact_data if x != None]
        data.loc[idx, "contact"] = " | ".join(contact_data)

        tmp_dists = []
        tmp_links = []
        for dist in data.loc[idx, "distribution"]:
            # remove line breaks of description since these break the comment blocks
            if dist["description"] != None:
                dist["description"] = re.sub(r"\n+", " ", dist["description"])
            md = [f"# {k.capitalize():<25}: {dist[k]}\n" for k in KEYS_DISTRIBUTION]
            tmp_dists.append("".join(md))
            tmp_links.append(dist["downloadUrl"])

        # use .at[] to properly add a list as value to row
        # https://stackoverflow.com/a/53299945/7117003
        data.at[idx, "distributions"] = tmp_dists
        data.at[idx, "distribution_links"] = tmp_links

    return data


def create_python_notebooks(data):
    """Create Jupyter Notebooks with Python starter code"""
    for idx in tqdm(data.index):
        with open(f"{TEMPLATE_FOLDER}{TEMPLATE_PYTHON}") as file:
            py_nb = file.read()

        # populate template with metadata
        identifier = data.loc[idx, "identifier"]
        py_nb = py_nb.replace("{{ PROVIDER }}", PROVIDER)
        py_nb = py_nb.replace("{{ DATASET_TITLE }}", re.sub(
            "\"", "\'", data.loc[idx, "title"]))

        py_nb = py_nb.replace("{{ DATASET_DESCRIPTION }}", re.sub(
            "\"", "\'", data.loc[idx, "description"]))
        py_nb = py_nb.replace("{{ DATASET_IDENTIFIER }}", identifier)
        py_nb = py_nb.replace("{{ DATASET_METADATA }}", re.sub(
            "\"", "\'", data.loc[idx, "metadata"]))
        py_nb = py_nb.replace("{{ DISTRIBUTION_COUNT }}", str(
            len(data.loc[idx, "distributions"])))

        ds_link = f'[Direct data shop link for dataset]({BASELINK_DATASHOP}{identifier})'
        py_nb = py_nb.replace("{{ DATASHOP_LINK }}", ds_link)
        py_nb = py_nb.replace("{{ CONTACT }}", data.loc[idx, "contact"])

        # to properly populate the code cell for data set import
        # we need to operate on the actual JSON rather than use simple string replacement
        py_nb = json.loads(py_nb, strict=False)

        # find predefined code cell for distributions
        # this cell contains just the string '{{ DISTRIBUTION }}'
        # this has to be set in the template
        for dist_idx, cell in enumerate(py_nb["cells"]):
            if cell["source"] == ['{{ DISTRIBUTION }}']:
                dist_cell_idx = dist_idx
                break

        # create metadata and code blocks for each CSV distribution
        code_block = []
        for id_dist, (dist, dist_link) in enumerate(zip(data.loc[idx, "distributions"], data.loc[idx, "distribution_links"])):
            code = f"# Distribution {id_dist}\n{dist}\ndf = get_dataset('{dist_link}')\n"
            code = "".join([f'{line}\n' for line in code.split("\n")])
            code_block.append(code)
        code_block = "".join(code_block)
        py_nb["cells"][dist_cell_idx]["source"] = code_block

        # save to disk
        with open(f'{TEMP_PREFIX}{REPO_PYTHON_OUTPUT}{identifier}.ipynb', 'w') as file:
            file.write(json.dumps(py_nb))


def create_rmarkdown(data):
    """Create R Markdown files with R starter code"""
    for idx in tqdm(data.index):
        with open(f"{TEMPLATE_FOLDER}{TEMPLATE_RMARKDOWN}") as file:
            rmd = file.read()

        # populate template with metadata
        identifier = data.loc[idx, "identifier"]
        rmd = rmd.replace("{{ DATASET_TITLE }}", data.loc[idx, "title"])
        rmd = rmd.replace("{{ PROVIDER }}", PROVIDER)
        rmd = rmd.replace("{{ TODAY_DATE }}", TODAY_DATE)
        rmd = rmd.replace("{{ DATASET_IDENTIFIER }}", identifier)
        rmd = rmd.replace("{{ DATASET_DESCRIPTION }}",
                          data.loc[idx, "description"])
        rmd = rmd.replace("{{ DATASET_METADATA }}", data.loc[idx, "metadata"])

        rmd = rmd.replace("{{ CONTACT }}", data.loc[idx, "contact"])
        rmd = rmd.replace("{{ DISTRIBUTION_COUNT }}", str(
            len(data.loc[idx, "distributions"])))

        ds_link = f'[Direct data shop link for dataset]({BASELINK_DATASHOP}{identifier})'
        rmd = rmd.replace("{{ DATASHOP_LINK }}", ds_link)

        # create code blocks for all distributions
        code_block = []
        for id_dist, (dist, dist_link) in enumerate(zip(data.loc[idx, "distributions"], data.loc[idx, "distribution_links"])):
            code = f"# Distribution {id_dist}\n{dist}\ndf <- read_delim('{dist_link}')\n\n"
            code_block.append(code)
        code_block = "".join(code_block)
        rmd = rmd.replace("{{ DISTRIBUTIONS }}", "".join(code_block))

        # save to disk
        with open(f'{TEMP_PREFIX}{REPO_R_MARKDOWN_OUTPUT}{identifier}.Rmd', 'w') as file:
            file.write("".join(rmd))


def get_header(dataset_count):
    """Retrieve header template and populate with date and count of data records"""
    with open(f"{TEMPLATE_FOLDER}{TEMPLATE_HEADER}") as file:
        header = file.read()
    header = re.sub("{{ DATASET_COUNT }}", str(int(dataset_count)), header)
    header = re.sub("{{ TODAY_DATE }}", TODAY_DATETIME, header)
    return header


def create_overview(data, header):
    """Create README with link table"""
    baselink_r_gh = f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_R_MARKDOWN_OUTPUT}"
    baselink_py_gh = f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}"
    baselink_py_colab = f"https://githubtocolab.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}"

    md_doc = []
    md_doc.append(header)
    md_doc.append(
        f"| ID | Title (abbreviated to {TITLE_MAX_CHARS} chars) | Python Colab | Python GitHub | R GitHub |\n")
    md_doc.append("| :-- | :-- | :-- | :-- | :-- |\n")

    for idx in tqdm(data.index):
        identifier = data.loc[idx, "identifier"]
        # remove square brackets from title, since these break markdown links
        title_clean = data.loc[idx, "title"].replace(
            "[", " ").replace("]", " ")
        if len(title_clean) > TITLE_MAX_CHARS:
            title_clean = title_clean[:TITLE_MAX_CHARS] + "…"

        ds_link = f'{BASELINK_DATASHOP}{identifier}'

        r_gh_link = f'[R GitHub]({baselink_r_gh}{identifier}.Rmd)'
        py_gh_link = f'[Python GitHub]({baselink_py_gh}{identifier}.ipynb)'
        py_colab_link = f'[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({baselink_py_colab}{identifier}.ipynb)'

        md_doc.append(
            f"| {identifier.split('@')[0]} | [{title_clean}]({ds_link}) | {py_colab_link} | {py_gh_link} | {r_gh_link} |\n")

    md_doc = "".join(md_doc)

    with open(f"{TEMP_PREFIX}README.md", "w") as file:
        file.write(md_doc)


# CREATE CODE FILES ---------------------------------------------------------- #

all_data = get_current_json()

df = filter_csv(all_data)
df = sort_data(df)
df = prepare_data_for_codebooks(df)

create_python_notebooks(df)
create_rmarkdown(df)

header = get_header(len(df))
create_overview(df, header)
