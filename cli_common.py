# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared CLI helpers for exporters and validation tools."""

import argparse
import logging as log
import os
from typing import Iterable, Optional

from dotenv import load_dotenv


load_dotenv()

DEFAULT_DIRECTORY_USERNAME = os.getenv("DIRECTORYUSERNAME")
DEFAULT_DIRECTORY_PASSWORD = os.getenv("DIRECTORYPASSWORD")
DEFAULT_DIRECTORY_TOKEN = os.getenv("DIRECTORYTOKEN")


class ExtendAction(argparse.Action):
    """Compatibility helper for Python versions without argparse extend."""

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


def build_parser(*args, **kwargs) -> argparse.ArgumentParser:
    """Create an ArgumentParser with the shared extend action registered."""
    parser = argparse.ArgumentParser(*args, **kwargs)
    parser.register("action", "extend", ExtendAction)
    return parser


def configure_logging(args) -> None:
    """Configure logging based on standard verbose/debug flags."""
    if args.debug:
        log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
    elif args.verbose:
        log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
    else:
        log.basicConfig(format="%(levelname)s: %(message)s")


def _add_hidden_aliases(
    parser: argparse.ArgumentParser,
    option_strings: Iterable[str],
    **kwargs,
) -> None:
    for option_string in option_strings:
        parser.add_argument(option_string, help=argparse.SUPPRESS, **kwargs)


def add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    """Add standard verbose/debug flags."""
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="verbose information about progress",
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        help="debug information about progress",
    )


def add_xlsx_output_argument(
    parser: argparse.ArgumentParser,
    *,
    dest: str = "outputXLSX",
    default_filename: Optional[str] = None,
    help_text: str = "write results to the provided XLSX file",
) -> None:
    """Add the shared primary XLSX output option."""
    default_value = [default_filename] if default_filename is not None else None
    parser.add_argument(
        "-X",
        "--output-xlsx",
        dest=dest,
        nargs=1,
        default=default_value,
        help=help_text,
    )
    _add_hidden_aliases(
        parser,
        ["--output-XLSX"],
        dest=dest,
        nargs=1,
    )


def add_optional_xlsx_output_argument(
    parser: argparse.ArgumentParser,
    *,
    dest: str,
    long_option: str,
    help_text: str,
    short_option: Optional[str] = None,
    legacy_long_options: Optional[Iterable[str]] = None,
) -> None:
    """Add an optional XLSX file path argument with optional legacy aliases."""
    option_strings = [long_option]
    if short_option is not None:
        option_strings.insert(0, short_option)
    parser.add_argument(*option_strings, dest=dest, nargs=1, help=help_text)
    if legacy_long_options:
        _add_hidden_aliases(
            parser,
            legacy_long_options,
            dest=dest,
            nargs=1,
        )


def add_no_stdout_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared stdout suppression flag."""
    parser.add_argument(
        "-N",
        "--no-stdout",
        dest="nostdout",
        action="store_true",
        help="suppress stdout output",
    )
    _add_hidden_aliases(
        parser,
        ["--output-no-stdout"],
        dest="nostdout",
        action="store_true",
    )


def add_validation_warning_argument(parser: argparse.ArgumentParser) -> None:
    """Add shared suppression for non-fatal local validation warnings."""
    parser.add_argument(
        "--suppress-validation-warnings",
        dest="suppress_validation_warnings",
        action="store_true",
        help="suppress non-fatal local validation warnings (config/cache/input normalization)",
    )


def add_withdrawn_scope_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_dest: str = "include_withdrawn",
    only_dest: str = "only_withdrawn",
    include_help_text: str = "include withdrawn entities in the check/export run",
    only_help_text: str = "run only on withdrawn entities",
) -> None:
    """Add shared flags for withdrawn-scope selection."""
    parser.add_argument(
        "-w",
        "--include-withdrawn",
        dest=include_dest,
        action="store_true",
        help=include_help_text,
    )
    parser.add_argument(
        "--only-withdrawn",
        dest=only_dest,
        action="store_true",
        help=only_help_text,
    )


def add_include_withdrawn_argument(
    parser: argparse.ArgumentParser,
    *,
    dest: str = "include_withdrawn",
    help_text: str = "include withdrawn entities in the check/export run",
) -> None:
    """Backward-compatible wrapper for include-withdrawn-only use."""
    add_withdrawn_scope_arguments(
        parser,
        include_dest=dest,
        only_dest="__unused_only_withdrawn",
        include_help_text=help_text,
        only_help_text=argparse.SUPPRESS,
    )


def add_purge_cache_arguments(
    parser: argparse.ArgumentParser,
    cache_choices,
    *,
    dest: str = "purgeCaches",
    include_purge_all: bool = True,
    include_purge_cache: bool = True,
) -> None:
    """Add shared cache purging options."""
    if include_purge_all:
        parser.add_argument(
            "--purge-all-caches",
            dest=dest,
            action="store_const",
            const=list(cache_choices),
            help="purge all configured caches",
        )
    if include_purge_cache:
        parser.add_argument(
            "--purge-cache",
            dest=dest,
            nargs="+",
            action="extend",
            choices=cache_choices,
            help="purge one or more configured caches",
        )


def add_directory_auth_arguments(parser: argparse.ArgumentParser) -> None:
    """Add username/password and token arguments for Directory login."""
    parser.add_argument(
        "-u",
        "--username",
        dest="username",
        default=DEFAULT_DIRECTORY_USERNAME,
        help="username of the account used to log in to the Directory",
    )
    parser.add_argument(
        "-p",
        "--password",
        dest="password",
        default=DEFAULT_DIRECTORY_PASSWORD,
        help="password of the account used to log in to the Directory",
    )
    parser.add_argument(
        "-t",
        "--token",
        dest="token",
        default=DEFAULT_DIRECTORY_TOKEN,
        help="access token for the Directory (alternative to username/password)",
    )


def add_directory_schema_argument(
    parser: argparse.ArgumentParser,
    *,
    default: str = "ERIC",
    dest: str = "schema",
) -> None:
    """Add the standard Directory schema/staging-area argument."""
    parser.add_argument(
        "-P",
        "--schema",
        dest=dest,
        default=default,
        help="Directory schema/staging area name",
    )
    _add_hidden_aliases(
        parser,
        ["--package"],
        dest=dest,
    )


def build_directory_kwargs(args, *, pp=None) -> dict:
    """Build normalized keyword arguments for Directory(...)."""
    include_withdrawn = bool(
        getattr(args, "include_withdrawn", False)
        or getattr(args, "only_withdrawn", False)
    )
    kwargs = {
        "schema": getattr(args, "schema", "ERIC"),
        "purgeCaches": getattr(args, "purgeCaches", []),
        "debug": getattr(args, "debug", False),
        "pp": pp,
        "include_withdrawn_entities": include_withdrawn,
        "only_withdrawn_entities": bool(getattr(args, "only_withdrawn", False)),
    }
    username = getattr(args, "username", None)
    password = getattr(args, "password", None)
    if username is not None and password is not None:
        kwargs["username"] = username
        kwargs["password"] = password
    token = getattr(args, "token", None)
    if token is not None:
        kwargs["token"] = token
    return kwargs


def add_remote_check_disable_arguments(
    parser: argparse.ArgumentParser,
    remote_check_choices,
    *,
    dest: str = "disableChecksRemote",
) -> None:
    """Add QC-only remote check disable arguments."""
    parser.add_argument(
        "-r",
        "--disable-checks-all-remote",
        dest=dest,
        action="store_const",
        const=list(remote_check_choices),
        help="disable all remote checks",
    )
    parser.add_argument(
        "--disable-checks-remote",
        dest=dest,
        nargs="+",
        action="extend",
        choices=remote_check_choices,
        help="disable one or more remote checks",
    )


def add_plugin_disable_argument(
    parser: argparse.ArgumentParser,
    plugin_choices,
    *,
    dest: str = "disablePlugins",
) -> None:
    """Add QC-only plugin disable argument."""
    parser.add_argument(
        "--disable-plugins",
        dest=dest,
        nargs="+",
        action="extend",
        choices=plugin_choices,
        help="disable one or more checks/plugins",
    )
