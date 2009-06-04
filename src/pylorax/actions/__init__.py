# pylorax/actions/__init__.py

import os


def getActions():
    actions = {}
    root, actions_dir = os.path.split(os.path.dirname(__file__))

    modules = set()
    for filename in os.listdir(os.path.join(root, actions_dir)):
        if filename.endswith('.py') and filename != '__init__.py':
            basename, extension = os.path.splitext(filename)
            modules.add(os.path.join('pylorax', actions_dir, basename).replace('/', '.'))

    for module in modules:
        print('Loading actions from %s' % module)
        imported = __import__(module, globals(), locals(), [module], -1)
        try:
            commands = getattr(imported, 'COMMANDS')
        except AttributeError:
            continue
        else:
            for command, classname in commands.items():
                print('Loaded: %s' % classname)
                actions[command] = getattr(imported, classname)

    return actions
