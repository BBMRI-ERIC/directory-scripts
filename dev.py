"""
Development script for testing the features of directory.py
"""
import os
from dotenv import load_dotenv

from directory import Directory


def main():
    load_dotenv()

    direc = Directory(schema="ERIC", token=os.environ.get("MOLGENIS_TOKEN"))


if __name__ == '__main__':
    main()
