"""Keep file-based Yapsy QC plugins runnable after removal of Python's imp API."""

import configparser
import hashlib
import importlib.util
import inspect
import logging
from pathlib import Path
import sys
from types import SimpleNamespace


class PortablePluginManager:
    """Provide the file-plugin manager operations used by the QC runner.

    This fallback deliberately does not replace Yapsy's broader management API.
    Plugin instances still implement the original Yapsy IPlugin interface.
    """

    def __init__(self, categories_filter):
        """Initialize discovery state for explicitly accepted plugin interfaces.

        Args:
            categories_filter: Category names mapped to required base classes.
        """
        self.categories_interfaces = dict(categories_filter)
        self._places = []
        self._plugins = []

    def setPluginPlaces(self, places):
        """Set directories containing local Yapsy descriptor files.

        Args:
            places: Iterable of directory paths to inspect without recursion.

        Returns:
            None.
        """
        self._places = [Path(place) for place in places]

    def collectPlugins(self):
        """Import declared local modules and instantiate their own plugin class.

        Returns:
            None. Invalid plugins are logged and skipped without disabling others.
        """
        self._plugins = []
        for place in self._places:
            for descriptor in sorted(place.glob("*.yapsy-plugin")):
                try:
                    config = configparser.ConfigParser()
                    config.read(descriptor, encoding="utf-8")
                    module_name = config.get("Core", "Module")
                    if Path(module_name).name != module_name:
                        raise ValueError("Plugin Module must name a local file")
                    path = descriptor.parent / (module_name + ".py")
                    key = "_directory_plugin_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()
                    spec = importlib.util.spec_from_file_location(key, path)
                    if spec is None or spec.loader is None:
                        raise ValueError("Plugin module has no supported loader")
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[key] = module
                    spec.loader.exec_module(module)
                    interfaces = tuple(self.categories_interfaces.values())
                    classes = [item for item in vars(module).values()
                               if inspect.isclass(item) and item.__module__ == key
                               and issubclass(item, interfaces)]
                    if len(classes) != 1:
                        raise ValueError("Plugin module must define exactly one compatible class")
                    self._plugins.append(SimpleNamespace(
                        name=config.get("Core", "Name"), path=str(path.with_suffix("")),
                        plugin_object=classes[0](),
                    ))
                except Exception as exc:
                    logging.getLogger(__name__).warning("Cannot load QC plugin %s: %s", descriptor.name, exc)

    def getAllPlugins(self):
        """Return discovered plugin records without exposing the mutable list.

        Returns:
            New list of records with name, path and plugin_object attributes.
        """
        return list(self._plugins)

    def activatePluginByName(self, name):
        """Activate a uniquely named discovered plugin.

        Args:
            name: Descriptor Core/Name of the plugin to activate.

        Returns:
            Activated IPlugin instance, or None if no record matches.
        """
        for plugin in self._plugins:
            if plugin.name == name:
                plugin.plugin_object.activate()
                return plugin.plugin_object
        return None


try:
    from yapsy.PluginManager import PluginManager
except ModuleNotFoundError as exc:
    if exc.name != "imp":
        raise
    PluginManager = PortablePluginManager
