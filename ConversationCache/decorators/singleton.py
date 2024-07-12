import functools


def singleton(cls):
    instances = {}

    @functools.wraps(cls)
    def get_instance(*args, **kwargs) -> cls:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
