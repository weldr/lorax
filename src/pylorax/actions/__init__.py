# pylorax/actions/__init__.py

import sys
import os


def getActions(verbose=False):
    actions = {}
    root, actions_dir = os.path.split(os.path.dirname(__file__))

    sys.path.insert(0, root)

    modules = set()
    for filename in os.listdir(os.path.join(root, actions_dir)):
        if filename.endswith('.py') and filename != '__init__.py':
            basename, extension = os.path.splitext(filename)
            modules.add(os.path.join(actions_dir, basename).replace('/', '.'))

    for module in modules:
        if verbose:
            print("Loading actions from module '%s'" % module)
        imported = __import__(module, globals(), locals(), [module], -1)

        try:
            commands = getattr(imported, 'COMMANDS')
        except AttributeError:
            if verbose:
                print("No actions found")
            continue
        else:
            for command, classname in commands.items():
                if verbose:
                    print("Loaded: %s" % classname)
                actions[command] = getattr(imported, classname)

    sys.path.pop(0)

    return actions
