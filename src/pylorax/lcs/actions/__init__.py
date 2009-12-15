#
# __init__.py
#

import sys
import os


def get_map():
    actions = {}

    root, actions_dir = os.path.split(os.path.dirname(__file__))

    sys.path.insert(0, root)

    modules = set()
    for filename in os.listdir(os.path.join(root, actions_dir)):
        if filename.endswith(".py") and not filename == "__init__.py":
            basename, extension = os.path.splitext(filename)
            modules.add(os.path.join(actions_dir, basename).replace("/", "."))

    for module in modules:
        imported = __import__(module, globals(), locals(), [module], -1)

        commands = getattr(imported, "COMMANDS", {})
        for command, classname in commands.items():
            actions[command] = getattr(imported, classname)

    sys.path.pop(0)

    return actions
