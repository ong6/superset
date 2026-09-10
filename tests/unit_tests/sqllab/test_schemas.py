# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import pytest
from marshmallow import Schema, ValidationError


def _execute_payload_schemas() -> list[Schema]:
    from superset.sqllab.schemas import ExecutePayloadSchema
    from superset.views.sql_lab.schemas import SqlJsonPayloadSchema

    return [ExecutePayloadSchema(), SqlJsonPayloadSchema()]


def _payload(query_limit: object) -> dict[str, object]:
    return {"database_id": 1, "sql": "SELECT 1", "queryLimit": query_limit}


@pytest.mark.parametrize("query_limit", [-1, -100, 1.5, 0.5])
def test_execute_schemas_reject_invalid_query_limit(query_limit: float) -> None:
    """
    Negative and fractional `queryLimit` values must fail validation instead of
    being coerced to 0 or forwarded as a float row limit.
    """
    for schema in _execute_payload_schemas():
        with pytest.raises(ValidationError):
            schema.load(_payload(query_limit))


@pytest.mark.parametrize("query_limit", [0, 1, 1000, None])
def test_execute_schemas_accept_valid_query_limit(query_limit: float) -> None:
    for schema in _execute_payload_schemas():
        result = schema.load(_payload(query_limit))
        assert result["queryLimit"] == query_limit


def test_sqllab_bootstrap_database_schema_includes_engine_information() -> None:
    """
    The OpenAPI contract for `GET /api/v1/sqllab/` documents `engine_information`
    (including `identifier_quote`) on each database entry, matching what
    `bootstrap_sqllab_data` actually returns.
    """
    from superset.sqllab.schemas import SQLLabBootstrapDatabaseSchema

    schema = SQLLabBootstrapDatabaseSchema()
    result = schema.dump(
        {
            "id": 1,
            "database_name": "my_database",
            "backend": "mysql",
            "allow_file_upload": False,
            "allow_ctas": False,
            "allow_cvas": False,
            "allow_dml": False,
            "allow_run_async": False,
            "allow_multi_catalog": False,
            "allows_cost_estimate": None,
            "allows_subquery": True,
            "allows_virtual_table_explore": True,
            "disable_data_preview": False,
            "disable_drill_to_detail": False,
            "expose_in_sqllab": True,
            "force_ctas_schema": None,
            "engine_information": {
                "supports_offset": True,
                "identifier_quote": {"start": "`", "end": "`"},
            },
        }
    )

    assert result["engine_information"] == {
        "supports_offset": True,
        "identifier_quote": {"start": "`", "end": "`"},
    }
