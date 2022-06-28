from dapla_dlp import find_filtered_fields, find_all_fields
import avro.schema
import pytest

testdata = [
    ('simple.avsc', 5),
    ('simple-nested.avsc', 3),
    ('remabong.avsc', 62),
    ('skattemelding-rawdata.avsc', 3508)
]

@pytest.mark.parametrize("filename,num_fields", testdata)
def test_find_fields_in_schemas(filename, num_fields):
    avro_schema = avro.schema.parse(open(f"tests/avro-schema/{filename}", "rb").read())
    fields = find_all_fields(avro_schema)
    assert len(fields) == num_fields


def test_filter_skattemelding():
    avro_schema = avro.schema.parse(open(f"tests/avro-schema/skattemelding-rawdata.avsc", "rb").read())
    fields = find_filtered_fields(avro_schema, ["**/opprettetDato"])
    assert len(fields) == 1
    fields = find_filtered_fields(avro_schema, ["**/*ersonidentifikator"])
    assert len(fields) == 113
