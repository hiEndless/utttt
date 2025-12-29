import importlib
import pkgutil
from event_center.indicators_event.plugins.base import Plugin
import event_center.indicators_event.plugins as plugins_pkg

def load_plugins():
    plugins = []

    for _, module_name, _ in pkgutil.iter_modules(plugins_pkg.__path__):
        if module_name == "base":
            continue

        module = importlib.import_module(f"event_center.indicators_event.plugins.{module_name}")

        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                # skip abstract classes
                if getattr(attr, "__abstractmethods__", set()):
                    continue
                plugins.append(attr())

    return plugins
