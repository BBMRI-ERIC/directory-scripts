"""
Development script for testing the features of directory.py
"""
import logging
import os
from dotenv import load_dotenv

from directory import Directory

logging.basicConfig(level=logging.DEBUG)

def main():
    load_dotenv()

    direc = Directory(schema="ERIC", token=os.environ.get("MOLGENIS_TOKEN"),
                      purgeCaches='directory', debug=True)


if __name__ == '__main__':
    main()
