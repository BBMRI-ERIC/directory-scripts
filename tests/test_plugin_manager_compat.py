"""Exercise file-based QC plugin discovery on Python without the imp module."""

import textwrap


def test_discovers_and_activates_declared_plugin(tmp_path):
    """Load only the declared local plugin class and preserve the runner interface.

    Args:
        tmp_path: Temporary directory holding one minimal Yapsy-style plugin.

    Returns:
        None.
    """
    from plugin_manager_compat import PluginManager
    from yapsy.IPlugin import IPlugin
    (tmp_path / "Example.py").write_text(textwrap.dedent('''
        from yapsy.IPlugin import IPlugin
        class Example(IPlugin):
            def check(self, directory, args):
                return []
    '''), encoding="utf-8")
    (tmp_path / "Example.yapsy-plugin").write_text("[Core]\nName = Example\nModule = Example\n", encoding="utf-8")
    manager = PluginManager(categories_filter={"Default": IPlugin})
    manager.setPluginPlaces([str(tmp_path)])
    manager.collectPlugins()
    plugin = manager.getAllPlugins()[0]
    assert plugin.name == "Example"
    assert plugin.plugin_object.check(None, None) == []
    manager.activatePluginByName("Example")
    assert plugin.plugin_object.is_activated
