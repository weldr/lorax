#
# singleton.py
#

class Singleton(object):

    __instance = None

    @classmethod
    def get(cls):
        if cls.__instance is None:
            cls.__instance = cls()

        return cls.__instance
