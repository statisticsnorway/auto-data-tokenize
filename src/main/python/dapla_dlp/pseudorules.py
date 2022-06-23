import avro.schema
from globmatch import glob_match

def find_filtered_fields(avro_schema, globs):
    """
    Find all fields in an avro_schema that matches a set of glob patterns. The results are represented as
    jsonpath expressions (e.g flattened).

    Example:
    --------
    Given an avro schema composed of fields:
    $.foo.bar.baz
    $.foo.bar.qux

    then:
    glob ´**/baz´ matches ´$.foo.bar.baz´
    glob ´**/bar/**´ matches ´$.foo.bar.baz, $.foo.bar.qux´

    For more glob expressions examples, see https://github.com/vidartf/globmatch#usage

    :param avro_schema: avro schema to traverse
    :param globs: glob expressions used to filter the fields
    :return: a set of "leaf fields" of an avro schema, filtered by a collection of glob expressions
    """
    all_fields = find_all_fields(avro_schema)
    all_paths = {_jsonpath_to_path(field) for field in all_fields}
    return {_path_to_jsonpath(p) for p in all_paths if glob_match(p, globs)}


def find_all_fields(avro_schema):
    """
    Traverse an avro schema and produce a set of all leaf fields that the schema is composed of - represented as
    jsonpath expressions (e.g flattened).

    Assumes that the starting avro schema is a "record".

    :param avro_schema: avro schema to traverse
    :return: a set of all "leaf fields" that an avro schema is composed of
    """
    fields = set()
    _traverse_record(avro_schema, "$", fields)
    return fields

def _traverse_record(record, namespace, fields):
    """
    Traverse an avro schema record and recursively collect all "leaf nodes" into the supplied set, expressed as jsonpath.

    :param record: avro schema record
    :param namespace: namespace to prefix all items with
    :param fields: set of already collected fields
    """
    if isinstance(record, avro.schema.RecordSchema) is False:
        raise ValueError(f'Expected avro record, encountered {type(record)}')

    namespace += "." + _item_name(record)

    for item in record.get_prop("fields"):
        if isinstance(item.type, avro.schema.PrimitiveSchema):
            jsonpath = f"{namespace}.{item.get_prop('name')}"
            fields.add(jsonpath)

        # Records
        elif isinstance(item.type, avro.schema.RecordSchema):
            _traverse_record(item.type, namespace, fields)

        # Arrays
        elif isinstance(item.type, avro.schema.ArraySchema):
            _traverse_array(item.type, namespace, fields)

        # Unions
        elif isinstance(item.type, avro.schema.UnionSchema):
            _traverse_union(item.type, f"{namespace}.{_item_name(item)}", fields)


def _traverse_union(union, namespace, fields):
    """
    Traverse an avro schema union and recursively collect all "leaf nodes" into the supplied set, expressed as jsonpath.

    :param union: avro schema union
    :param namespace: namespace to prefix all items with
    :param fields: set of already collected fields
    """
    if isinstance(union, avro.schema.UnionSchema) is False:
        raise ValueError(f'Expected avro union, encountered {type(union)}')

    # Treat as "leaf node" if the union is exclusively composed of primitives
    if all(isinstance(schema, avro.schema.PrimitiveSchema) for schema in union.schemas):
        fields.add(namespace)
    else:
        for schema in union.schemas:
            if isinstance(schema, avro.schema.RecordSchema):
                _traverse_record(schema, namespace, fields)
            elif isinstance(schema, avro.schema.ArraySchema):
                _traverse_array(schema, namespace, fields)


def _traverse_array(arr, namespace, fields):
    """
    Traverse an avro schema array and recursively collect all "leaf nodes" into the supplied set, expressed as jsonpath.

    :param arr: avro schema array
    :param namespace: namespace to prefix all items with
    :param fields: set of already collected fields
    """
    if isinstance(arr, avro.schema.ArraySchema) is False:
        raise ValueError(f'Expected avro array, encountered {type(arr)}')

    items = arr.get_prop("items")
    if isinstance(items, avro.schema.RecordSchema):
        _traverse_record(items, namespace, fields)
    elif isinstance(items, avro.schema.PrimitiveSchema) is False:
        raise ValueError(f"Unexpected type in array: {type(items)}")


def _item_name(schema_item):
    """
    Produce the qualified name of an avro item, using a combination of namespace and name.

    Note that when computing the qualified item_name we're only considering item in question (e.g. not its parents)

    Examples:
    * if the item's namespace is "foo.bar" and its name is "baz" then item_name yields "foo.bar.baz"
    * if the item's namespace is not defined and its name is "baz" then item_name yields "baz"

    :param schema_item: an avro schema item
    :return: a namespace qualified name of an avro item
    """
    return ".".join(filter(None, [schema_item.get_prop("namespace"), schema_item.get_prop("name")]))


def _jsonpath_to_path(jsonpath):
    """
    Convert jsonpath expression to a path expression

    Example: $.foo.bar.baz --> /foo/bar/baz

    :param jsonpath: jsonpath expression to convert
    :return: path (slash separated, like in a file path)
    """
    return jsonpath.replace(".", "/")[1:]


def _path_to_jsonpath(path):
    """
    Convert slash separated path (like in a file path) to json path

    Example: /foo/bar/baz --> $.foo.bar.baz

    :param path: path to convert
    :return: jsonpath expression
    """
    return "$" + path.replace("/", ".")
