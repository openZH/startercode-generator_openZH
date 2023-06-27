# 🚀 Starter Code Generator OpenZH

### Automatically generate Python and R starter code for Open Government Data Shops


## Overview
This repo provides a Python script that generates starter code notebooks from a metadata JSON of open data shops. You can execute the script manually or trigger it regularly (e.g. every night) with a GitHub Action that we provide here too and by that create code notebooks for every dataset in your data shop. 

The script also generates a README file that contains a list of all datasets and links to the corresponding notebooks that you can use as an overview for your users. You can expose this easily as a website with GitHub Pages.

The execution of the script is lightweight and takes only a couple of minutes depending on the count of datasets in your data portal.

Your users get notebooks that are specifically tailored for every one of your datasets. They are already set with the most recent data set metadata and code snippets. Your user can start their analysis for your data sets right away with just a couple of clicks or even just one single click if they use Google Colab.

The result looks like [this](https://github.com/openZH/starter-code-openZH).


## How does it work?
The system works with two repos. 
- The **first repo** contains the code from this repo here that creates the notebooks and the overview README. 
- A GitHub Actin workflow instantiates a container, installs the necessary dependencies, clones the repo, and executes the script. 
- Once the notebooks are created the workflow will push these to a **second repo** that you can make available for your users.

The script works with templates that are stored in – you gessed it – `_templates`. You easily can adapt these according to your ideas. Just make sure that you keep the necessary placeholders (marked with double curly brackets) in the templates. The script will replace them with values from the metadata JSON.

The code works out of the box with the [metadata API of the open data shop of the Canton of Zurich](https://www.web.statistik.zh.ch/ogd/datenkatalog/standalone/datasets/1461@fachstelle-ogd-kanton-zuerich). It can be easily adapted to other data shops. E.g. [here is a repo with starter code notebooks for all CSV data set on opendata.swiss](https://github.com/rnckp/starter-code_opendataswiss).


## How to adapt the code to your needs?
-   Clone this repo and commit/push it to your GitHub account.
-   Create a second repo where you want to store the results.
-   Adapt the constants in `updater.py` to your account information, repo names, etc.
-   Adapt the parsing functions in `updater.py` to your metadata API.
-   Adapt the workflow file (see `.github/workflows/autoupdater.yml`):
    -   Set the cron pattern.
    -   Set the values for `destination-github-username` (the name of your GitHub account) and `destination-repository-name` (the name of the mentioned second repo that receives the results).
-   In your GitHub account go to `Settings > Developer settings > Personal access tokens > Fine-grained tokens` and create a new token by clicking `Generate new token`.
    -   Set a token name and set the expiration.
    -   Set `Repository access` to `Only select repositories`. Select both repositories and set permissions to `Read access to metadata` and `Read and Write access to code`.
    -   Copy the token.
-   In your GitHub account go to `Settings > Secrets` and create a new secret by clicking `New repository secret`.
    -   Set the name to `PAT` and paste the token you just copied. If you name your secret differently you need to adapt the workflow file accordingly.
-   Manually trigger the GitHub Action workflow and check the results.
-   Do not forget to add a licence to your second repo.


## Good to know
The wonderful people of the [OGD team Thurgau](https://ogd.tg.ch/) have created a [similar project](https://github.com/ogdtg/starter-code-ogdtg).


## Collaboration
Your ideas and contributions are very welcome. Please open an issue or a pull request.


## Credits
This repo is inspired and based on the work of (in alphabetical order) [Patrick Arnecke](https://github.com/rnckp), [Philipp Bosch](https://github.com/philbosch), [Stefan Oderbolz](https://github.com/metaodi/metaodi), [Adrian Rupp](https://github.com/adrianrupp88) and [Laure Stadler](https://github.com/stadlaur).