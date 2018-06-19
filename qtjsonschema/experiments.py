from contextlib import contextmanager
from functools import partial

from jsonschema import Draft4Validator, ValidationError
from jsonschema.validators import extend


class PathContext:

    def __init__(self):
        self._stack = []

    @contextmanager
    def __call__(self, component: str):
        if component is not None:
            self._stack.append(component)
        yield
        if component is not None:
            self._stack.pop()

    @property
    def current_string(self) -> str:
        return "/".join(map(str, self._stack))


schema_ctx = PathContext()
instance_ctx = PathContext()


_meta_results = []


def pop_meta_result():
    return (_meta_results or [None]).pop()


def push_meta_result(path, result):
    _meta_results.append((path, result))


def descend(_descend, instance, schema, path=None, schema_path=None):
    with instance_ctx(path), \
         schema_ctx(schema_path):
        yield from _descend(instance, schema, path, schema_path)


def validator_one_of(validator, one_of, instance, schema):
    sub_schemas = enumerate(one_of)
    all_errors = []
    for index, sub_schema in sub_schemas:
        errs = list(validator.descend(instance, sub_schema, schema_path=index))
        if not errs:
            first_valid = sub_schema
            push_meta_result(instance_ctx.current_string, first_valid)
            break
        all_errors.extend(errs)
    else:
        yield ValidationError(
            "%r is not valid under any of the given schemas" % (instance,),
            context=all_errors,
        )

    more_valid = [s for i, s in sub_schemas if validator.is_valid(instance, s)]
    if more_valid:
        print([more_valid])
        more_valid.append(first_valid)
        reprs = ", ".join(repr(schema) for schema in more_valid)
        yield ValidationError(
            "%r is valid under each of %s" % (instance, reprs)
        )


def validator_any_of(validator, any_of, instance, schema):
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
                   validators={"anyOf": validator_any_of,
                               "oneOf": validator_one_of})


if __name__ == "__main__":
    test_schema = {
        "title": "Person",
        "type": "object",
        "properties": {
            "users": {
                "type": "array",
                "items": {
                    "oneOf": [{"type": "integer"},
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
    for error in validator.iter_errors(test_data):
        raise error

    for result in iter(pop_meta_result, None):
        print("result", result)
