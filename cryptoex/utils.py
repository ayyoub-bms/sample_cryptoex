import json
import time
from functools import wraps


def assign_dtypes(default="float", **dtypes):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            dataframe = func(*args, **kwargs)
            custom_columns = dtypes.keys()
            if dataframe is not None:
                for t in list(dtypes.keys()):
                    if dtypes[t] == "int":
                        dataframe = dataframe.astype({t: "float"}).astype({t: "int"})
                        del dtypes[t]
                default_columns = dataframe.columns.difference(custom_columns)

                for c in default_columns:
                    dtypes[c] = default

                dataframe = dataframe.astype(dtypes)
            return dataframe

        return wrapper

    return decorator


def build_message(**kwargs) -> str:
    return json.dumps(kwargs)


def get_timestamp() -> int:
    return int(time.time() * 1000)


def overrides(iclass):
    def overrider(method):
        method_name = method.__name__
        assert method_name in dir(
            iclass
        ), f"There is no method {method_name} in parent class {iclass.__name__}"
        return method

    return overrider
