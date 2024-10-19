# Shopify Products Search CLI

## [FOR FIRST TIME SETUP] Setup pyenv, create a virtual environment with pyenv-virtualenv plugin, install poetry, and initialize project

- `curl https://pyenv.run | bash` (see [pyenv](https://github.com/pyenv/pyenv) for details on installation)
- if on macOS: `brew install pyenv-virtualenv`. Otherwise, see [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv) for details on installation.
- `pyenv install 3.12`
- `pyenv virtualenv 3.12 sps-v312`
- `pyenv activate sps-v312`
- `pyenv local sps-v312`
- `pip install poetry`
- `poetry config virtualenvs.create false`
- `poetry init`

## [FOR FIRST TIME SETUP] Install dependencies and activate shell

- `poetry install`
- `poetry shell`

## Run CLI

- to list all commands: `sps`
- to create a new shop: `sps shop create <identifier>` where `<identifier>` is the URL or hostname of the shop
- to list all shops: `sps shop ls`
- to import data from a directory: `sps import <directory>` where `<directory>` is the path to the directory containing the data
