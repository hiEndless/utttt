import pkgutil
from importlib import import_module

_plugins = []


def register_plugin(cls):
    _plugins.append(cls())
    return cls


def get_plugins():
    try:
        for _, name, _ in pkgutil.iter_modules(__path__):
            import_module(__name__ + "." + name)
    except Exception:
        pass
    return list(_plugins)