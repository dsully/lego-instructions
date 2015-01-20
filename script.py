#!/usr/bin/env python

""" Download LEGO PDF instructions from using the brickset.com API """

import os
import sys
import traceback

import click
from bs4 import BeautifulSoup
from clint.textui import progress
from iniparse import INIConfig
import requests

API_URL = 'http://brickset.com/api/v2.asmx'
API_KEY = 'eQod-Siva-aL4b'
INI_FILE = os.path.expanduser('~/.lego-instructions.ini')

# V39 is 8.5" x 11". V29 is A4
DEFAULT_PAPER_SIZE = 'V39'


def read_config():
  """
    Read the local configuration file & return an INIConfig object.

    :rtype: INIConfig
  """

  try:
    return INIConfig(open(INI_FILE))
  except IOError:

    print "Creating default config file at: {0}".format(INI_FILE)
    print "Please edit before continuing."

    config = INIConfig()
    config.brickset.username = 'brickset.com username'
    config.brickset.password = 'brickset.com password'
    config.brickset.papersize = DEFAULT_PAPER_SIZE
    config.download.path = '~/Documents/LEGO'

    with open(INI_FILE, 'w') as fh:
      print >> fh.write(str(config))

    sys.exit(1)


def download(url, path):
  """
    Download a given URL to the specified path.

    :param str url: The URL to download.
    :param str path: The file path to download to. Should be a directory.
    :return: The filename we saved to.
    :rtype: str
  """

  print "Downloading {0} to {1}".format(url, path)

  buffering = 4096
  filename = os.path.join(os.path.expanduser(path), url.split('/')[-1])
  response = requests.get(url, stream=True)

  response.raise_for_status()

  total_length = int(response.headers.get('content-length'))

  with open(filename, 'wb', buffering=buffering) as fh:

    for chunk in progress.bar(response.iter_content(chunk_size=buffering), expected_size=(total_length / buffering) + 1):
      if chunk:
        fh.write(chunk)

  return filename


def login(config):
  """
    Login to the Brickset API service.

    :param INIConfig config: A configuration object containing the API Key, username & password.
    :return: The 'userHash' token from the Brickset API.
    :rtype: str
  """

  response = requests.post(API_URL + '/login', data={
    'apiKey': API_KEY,
    'username': config.brickset.username,
    'password': config.brickset.password
  })

  response.raise_for_status()

  return BeautifulSoup(response.text).find('string').text


def get_sets(item, token):
  """
    Fetch the Brickset "Sets" using the lego "Set ID" as the query.

    :param int item: The LEGO Set ID. This is the number on the front of the LEGO package.
    :param str token: The Brickset userHash token.
    :return: The name of the set & the set ID.
    :rtype: str, str
  """

  response = requests.post(API_URL + '/getSets', data={
    'query': item,
    'apiKey': API_KEY,
    'userHash': token,
    'theme': '',
    'subtheme': '',
    'setNumber': '',
    'year': '',
    'owned': '',
    'wanted': '',
    'orderBy': '',
    'pageSize': 20,
    'pageNumber': 1,
    'userName': '',
  })

  response.raise_for_status()

  matches = set()

  for element in BeautifulSoup(response.text).find_all('sets'):
    matches.add((element.find('name').text, element.find('setid').text))

  return matches


def save_instructions(config, name, set_id):
  """
    Download the PDF file(s) with the given name and set ID.

    :param INIConfig config:
    :param str name: The set name.
    :param str set_id: The set ID.
  """

  response = requests.post(API_URL + '/getInstructions', data={
    'setID': str(set_id),
    'apiKey': API_KEY,
  })

  response.raise_for_status()

  soup = BeautifulSoup(response.text)
  urls = []

  for i in soup.find_all('instructions'):
    if config.brickset.papersize in i.find('description').text:
      urls.append(i.find('url').text)

  if not urls:
    raise ValueError("Couldn't find any PDFs for {0}/{1}".format(name, set_id))

  path = os.path.join(os.path.expanduser(config.download.path), "{0} {1}".format(set_id, name))

  if not os.path.exists(path):
    os.makedirs(path)

  for url in urls:
    download(url, path)

  print


@click.command()
@click.argument('set_id')
def cli(set_id):
  """ Download LEGO PDFs using the set ID. """

  try:
    config = read_config()
    token = login(config)

    sets = get_sets(set_id, token)

    if not sets:
      raise ValueError("Couldn't find any Brickset sets matching: {0}".format(set_id))

    for name, set_id in sets:
      save_instructions(config, name, set_id)

  except Exception as e:
    traceback.print_exc()
    sys.exit(e)
