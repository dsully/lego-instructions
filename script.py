#!/usr/bin/env python

"""Download LEGO PDF instructions from using the brickset.com API."""

import sys
import traceback
from pathlib import Path
from typing import Final

import click
import httpx
from bs4 import BeautifulSoup
from iniparse import INIConfig
from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn

API_URL: Final = "http://brickset.com/api/v2.asmx"
API_KEY: Final = "eQod-Siva-aL4b"
INI_FILE = Path("~/.lego-instructions.ini").expanduser()

# V39 is 8.5" x 11". V29 is A4
DEFAULT_PAPER_SIZE = "V39"


def read_config() -> INIConfig:
    """Read the local configuration file & return an INIConfig object.

    :rtype: INIConfig
    """

    try:
        return INIConfig(INI_FILE.open())
    except OSError:
        print(f"Creating default config file at: {INI_FILE}")
        print("Please edit before continuing.")

        config = INIConfig()
        config.brickset.username = "brickset.com username"
        config.brickset.password = "brickset.com password"
        config.brickset.papersize = DEFAULT_PAPER_SIZE
        config.download.path = "~/Documents/LEGO"

        INI_FILE.write_text(str(config))

        sys.exit(1)


def download(url: str, path: Path) -> None:
    """Download a given URL to the specified path.

    :param url: The URL to download.
    :param path: The file path to download to. Should be a directory.
    :return: The filename we saved to.
    """

    print(f"Downloading {url} to {path}")

    filename = path.joinpath(url.split("/")[-1])

    with filename.open("wb") as fh, httpx.stream("GET", url) as response:
        total = int(response.headers["Content-Length"])

        with Progress(
            "[progress.percentage]{task.percentage:>3.0f}%",
            BarColumn(bar_width=None),
            DownloadColumn(),
            TransferSpeedColumn(),
        ) as progress:
            download_task = progress.add_task("Download", total=total)

            for chunk in response.iter_bytes():
                fh.write(chunk)
                progress.update(download_task, completed=response.num_bytes_downloaded)


def login(config: INIConfig) -> str:
    """Login to the Brickset API service.

    :param INIConfig config: A configuration object containing the API Key, username & password.
    :return: The 'userHash' token from the Brickset API.
    :rtype: str
    """

    response = httpx.post(
        API_URL + "/login",
        data={
            "apiKey": API_KEY,
            "username": config.brickset.username,
            "password": config.brickset.password,
        },
    )

    response.raise_for_status()

    return BeautifulSoup(response.text).find("string").text


def get_sets(item: str, token: str) -> set[tuple[str, str]]:
    """Fetch the Brickset "Sets" using the lego "Set ID" as the query.

    :param int item: The LEGO Set ID. This is the number on the front of the LEGO package.
    :param str token: The Brickset userHash token.
    :return: The name of the set & the set ID.
    :rtype: str, str
    """

    response = httpx.post(
        API_URL + "/getSets",
        data={
            "query": item,
            "apiKey": API_KEY,
            "userHash": token,
            "theme": "",
            "subtheme": "",
            "setNumber": "",
            "year": "",
            "owned": "",
            "wanted": "",
            "orderBy": "",
            "pageSize": 20,
            "pageNumber": 1,
            "userName": "",
        },
    )

    response.raise_for_status()

    matches: set[tuple[str, str]] = set()

    for element in BeautifulSoup(response.text).find_all("sets"):
        matches.add((element.find("name").text, element.find("setid").text))

    return matches


def save_instructions(config: INIConfig, name: str, set_id: str) -> None:
    """Download the PDF file(s) with the given name and set ID.

    :param config:
    :param name: The set name.
    :param set_id: The set ID.
    """

    response = httpx.post(API_URL + "/getInstructions", data={"setID": set_id, "apiKey": API_KEY})

    soup = BeautifulSoup(response.text)
    urls = []

    for i in soup.find_all("instructions"):
        if config.brickset.papersize in i.find("description").text:
            urls.append(i.find("url").text)

    if not urls:
        raise ValueError(f"Couldn't find any PDFs for {name}/{set_id}")

    path = Path(config.download.path).expanduser() / f"{set_id} {name}"
    path.mkdir(parents=True, exist_ok=True)

    for url in urls:
        download(url, path)

    print()


@click.command()
@click.argument("set_id", type=str)
def cli(set_id: str):
    """Download LEGO PDFs using the set ID."""

    try:
        config = read_config()
        token = login(config)

        sets = get_sets(set_id, token)

        if not sets:
            raise ValueError(f"Couldn't find any Brickset sets matching: {set_id}")

        for name, sid in sets:
            save_instructions(config, name, sid)

    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.exit(1)
