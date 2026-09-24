# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared CLI helpers for exporters and validation tools."""

import argparse
import logging as log
import os
from typing import Iterable, Optional

from dotenv import load_dotenv
from fact_sheet_utils import NO_STAR_FACT_SUMS_WARNING


load_dotenv()

DEFAULT_DIRECTORY_USERNAME = os.getenv("DIRECTORYUSERNAME")
DEFAULT_DIRECTORY_PASSWORD = os.getenv("DIRECTORYPASSWORD")
DEFAULT_DIRECTORY_TOKEN = os.getenv("DIRECTORYTOKEN")


class ExtendAction(argparse.Action):
    """Implement argparse's extend action for callers needing legacy support."""

    def __call__(self, parser, namespace, values, option_string=None):
        """Append parsed values to the namespace destination.

        Args:
            parser: Parser dispatching this action; it is not otherwise used.
            namespace: Parsed namespace mutated at this action's destination.
            values: Iterable of values produced for the option occurrence.
            option_string: Option spelling that triggered the action, unused here.

        Returns:
            None. Mutates `namespace.<dest>` to a list containing prior and new values.
        """
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


def build_parser(*args, **kwargs) -> argparse.ArgumentParser:
    """Create an ArgumentParser with the shared extend action registered.

    Args:
        *args: Positional arguments forwarded unchanged to `argparse.ArgumentParser`.
        **kwargs: Keyword arguments forwarded unchanged to `argparse.ArgumentParser`.

    Returns:
        New parser with `action="extend"` registered to use `ExtendAction`.
    """
    parser = argparse.ArgumentParser(*args, **kwargs)
    parser.register("action", "extend", ExtendAction)
    return parser


def configure_logging(args) -> None:
    """Configure logging based on standard verbose/debug flags.

    Args:
        args: Namespace exposing `debug` and `verbose` booleans. Debug takes
            precedence over verbose.

    Returns:
        None. Configures the process root logger through `logging.basicConfig`.
    """
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
    """Register suppressed-help aliases with identical argument configuration.

    Args:
        parser: Parser mutated by `add_argument` calls.
        option_strings: Legacy option spellings to register without help output.
        **kwargs: Argument configuration shared by every alias.

    Returns:
        None. Mutates `parser` by adding each hidden alias.
    """
    for option_string in option_strings:
        parser.add_argument(option_string, help=argparse.SUPPRESS, **kwargs)


def add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    """Add standard verbose/debug flags.

    Args:
        parser: Parser receiving `-v/--verbose` and `-d/--debug` store-true flags.

    Returns:
        None. Mutates `parser` with standard logging destinations `verbose` and `debug`.
    """
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
    """Add the shared primary XLSX output option.

    Args:
        parser: Parser receiving the primary XLSX output option.
        dest: Namespace attribute holding a one-item path list or `None`.
        default_filename: Optional default path wrapped into the same one-item list.
        help_text: Help text for the visible option.

    Returns:
        None. Registers `-X/--output-xlsx` and a hidden `--output-XLSX` alias.
    """
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
    """Add an optional XLSX file path argument with optional legacy aliases.

    Args:
        parser: Parser receiving this output option.
        dest: Namespace attribute holding the supplied one-item path list.
        long_option: Visible long option spelling.
        help_text: Help text for the visible option.
        short_option: Optional visible short option spelling inserted before the long one.
        legacy_long_options: Optional hidden aliases with the same destination.

    Returns:
        None. Mutates `parser` with the configured option and aliases.
    """
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
    """Add the shared stdout suppression flag.

    Args:
        parser: Parser receiving the stdout-suppression flag.

    Returns:
        None. Registers `-N/--no-stdout` and the hidden legacy alias at `nostdout`.
    """
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


def add_fact_sheet_summary_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the explicit opt-in for assumption-violating no-star sums.

    Args:
        parser: Parser receiving the unsafe no-star fact-sheet fallback opt-in.

    Returns:
        None. Registers a store-true `allow_no_star_fact_sums` namespace field.
    """
    parser.add_argument(
        "--allow-no-star-fact-sums",
        dest="allow_no_star_fact_sums",
        action="store_true",
        help=(
            "derive missing fact-sheet marginal distributions by summing fully "
            "concrete no-star rows (unsafe: rows may overlap or be incomplete)"
        ),
    )


def warn_if_no_star_fact_sums_enabled(args) -> None:
    """Log the common unsafe-fallback warning when the opt-in is enabled.

    Args:
        args: Namespace that may expose `allow_no_star_fact_sums`.

    Returns:
        None. Emits the canonical warning through module logging only when opted in.
    """
    if getattr(args, "allow_no_star_fact_sums", False):
        log.warning(NO_STAR_FACT_SUMS_WARNING)


def add_validation_warning_argument(parser: argparse.ArgumentParser) -> None:
    """Add shared suppression for non-fatal local validation warnings.

    Args:
        parser: Parser receiving the local-validation-warning suppression flag.

    Returns:
        None. Registers a store-true `suppress_validation_warnings` field.
    """
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
    """Add shared flags for withdrawn-scope selection.

    Args:
        parser: Parser receiving the two withdrawn-scope flags.
        include_dest: Destination set by `-w/--include-withdrawn`.
        only_dest: Destination set by `--only-withdrawn`; callers resolve its
            relationship to include scope.
        include_help_text: Visible help for the include flag.
        only_help_text: Visible help for the only-withdrawn flag, or suppression text.

    Returns:
        None. Mutates `parser`; the flags are deliberately not an argparse mutex.
    """
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
    """Backward-compatible wrapper for include-withdrawn-only use.

    Args:
        parser: Parser receiving the compatibility include-withdrawn option.
        dest: Namespace destination for the include flag.
        help_text: Visible help text for that flag.

    Returns:
        None. Delegates registration and hides an unused only-withdrawn option.
    """
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
    """Add shared cache purging options.

    Args:
        parser: Parser receiving one or both cache-purge options.
        cache_choices: Iterable of permitted cache names. It is copied for the
            all-caches constant and used as choices for selected caches.
        dest: Namespace destination for the selected cache-name list.
        include_purge_all: Whether to register `--purge-all-caches`.
        include_purge_cache: Whether to register `--purge-cache`.

    Returns:
        None. Mutates `parser`; selected values extend through the registered action.
    """
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
    """Add username/password and token arguments for Directory login.

    Args:
        parser: Parser receiving username, password, and token options whose defaults
            were read from the environment at module import.

    Returns:
        None. Registers `-u/-p/-t` authentication destinations; token is an
        alternative to username/password for downstream connection builders.
    """
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
    """Add the standard Directory schema/staging-area argument.

    Args:
        parser: Parser receiving schema selection and emergency DAG bypass flags.
        default: Default Directory schema/staging-area name.
        dest: Namespace destination for the visible schema option and hidden alias.

    Returns:
        None. Registers `-P/--schema`, hidden `--package`, and
        `emergency_skip_dag_checks`.
    """
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
    parser.add_argument(
        "--emergency-skip-dag-checks",
        dest="emergency_skip_dag_checks",
        action="store_true",
        help=(
            "emergency mode: skip Directory hierarchy DAG acyclicity checks so "
            "the tool can proceed at own risk when live data contains a cycle"
        ),
    )


def build_directory_kwargs(args, *, pp=None) -> dict:
    """Build normalized keyword arguments for Directory(...).

    Args:
        args: Namespace whose optional common CLI fields are read defensively.
        pp: Optional progress/printer object passed through as `pp`.

    Returns:
        New keyword mapping for `Directory(...)`. `only_withdrawn` implies
        `include_withdrawn_entities`; credentials are included only when present.
    """
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
        "skip_graph_dag_validation": bool(
            getattr(args, "emergency_skip_dag_checks", False)
        ),
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
    """Add QC-only remote check disable arguments.

    Args:
        parser: Parser receiving remote-check disable options.
        remote_check_choices: Allowed remote check identifiers; all identifiers are
            copied into the all-remote constant.
        dest: Namespace destination holding selected identifiers.

    Returns:
        None. Registers `-r/--disable-checks-all-remote` and the extendable
        `--disable-checks-remote` option.
    """
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
    """Add QC-only plugin disable argument.

    Args:
        parser: Parser receiving the plugin-disable option.
        plugin_choices: Allowed plugin/check identifiers enforced by argparse.
        dest: Namespace destination holding the extended selection.

    Returns:
        None. Registers the extendable `--disable-plugins` option.
    """
    parser.add_argument(
        "--disable-plugins",
        dest=dest,
        nargs="+",
        action="extend",
        choices=plugin_choices,
        help="disable one or more checks/plugins",
    )
