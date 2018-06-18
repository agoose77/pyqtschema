from contextlib import contextmanager
from functools import partial

from jsonschema import Draft4Validator, ValidationError
from jsonschema.validators import extend


class PathContext:

    def __init__(self):
        self._stack = []

    @contextmanager
    def __call__(self, component: str):
        self._stack.append(component)
        yield
        self._stack.pop()

    @property
    def current_string(self) -> str:
        return "/".join(map(str, self._stack))


schema_ctx = PathContext()
instance_ctx = PathContext()


def push_meta_result(path, result):
    print("Meta", path, result)


def descend(_descend, instance, schema, path=None, schema_path=None):
    with instance_ctx(path), \
         schema_ctx(schema_path):
        yield from _descend(instance, schema, path, schema_path)


def _validator_any_of(validator, any_of, instance, schema):
    all_errors = []
    for index, sub_schema in enumerate(any_of):
        errs = list(validator.descend(instance, sub_schema, schema_path=index))
        if not errs:
            break
        all_errors.extend(errs)
    else:
        yield ValidationError(
            "%r is not valid under any of the given schemas" % (instance,),
            context=all_errors,
        )
    push_meta_result(instance_ctx.current_string, sub_schema)


Validator = extend(Draft4Validator,
                   validators={"anyOf": _validator_any_of})


if __name__ == "__main__":
    test_schema = {
        "title": "Person",
        "type": "object",
        "properties": {
            "users": {
                "type": "array",
                "items": {
                    "anyOf": [{"type": "integer"},
                              {"$ref": "#/definitions/name_list"}],
                }
            }
        },
        "required": ["users"],
        "definitions": {
            "name_list": {"type": "array", "items": {"type": "string"}},
        }
    }

    test_data = {
        'users': [["Jack", "Jill"], 1, 9]
    }

    validator = Validator(test_schema)
    validator.descend = partial(descend, validator.descend)
    validator.validate(test_data)
