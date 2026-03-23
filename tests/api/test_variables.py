"""Unit tests for Variable manager."""

import pytest
from unittest.mock import AsyncMock

from onshape_mcp.api.variables import VariableManager, Variable


class TestVariable:
    """Test Variable model."""

    def test_variable_creation_with_description(self):
        """Test creating a variable with description."""
        var = Variable(name="width", expression="10 in", description="Part width")

        assert var.name == "width"
        assert var.expression == "10 in"
        assert var.description == "Part width"

    def test_variable_creation_without_description(self):
        """Test creating a variable without description."""
        var = Variable(name="height", expression="5 in")

        assert var.name == "height"
        assert var.expression == "5 in"
        assert var.description is None

    def test_variable_requires_name(self):
        """Test that name is required."""
        with pytest.raises(Exception):
            Variable(expression="10 in")

    def test_variable_requires_expression(self):
        """Test that expression is required."""
        with pytest.raises(Exception):
            Variable(name="width")


class TestVariableManager:
    """Test VariableManager operations."""

    @pytest.fixture
    def variable_manager(self, onshape_client):
        """Provide a VariableManager instance."""
        return VariableManager(onshape_client)

    @pytest.mark.asyncio
    async def test_get_variables_success(
        self, variable_manager, onshape_client, sample_document_ids, sample_variables
    ):
        """Test getting variables from a Variable Studio response."""
        onshape_client.get = AsyncMock(
            side_effect=[
                [{"id": sample_document_ids["element_id"], "elementType": "VARIABLESTUDIO"}],
                [{"variableStudioReference": None, "variables": sample_variables}],
            ]
        )

        result = await variable_manager.get_variables(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
        )

        assert len(result) == 2
        assert all(isinstance(v, Variable) for v in result)

        # Check first variable
        assert result[0].name == "width"
        assert result[0].expression == "10 in"
        assert result[0].description == "Width of the part"

        # Check second variable
        assert result[1].name == "height"
        assert result[1].expression == "5 in"

        # Verify correct path
        call_args = onshape_client.get.call_args_list[1]
        path = call_args[0][0]
        assert "/variables" in path

    @pytest.mark.asyncio
    async def test_get_variables_empty_list(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test getting variables when none exist."""
        onshape_client.get = AsyncMock(
            side_effect=[
                [{"id": sample_document_ids["element_id"], "elementType": "VARIABLESTUDIO"}],
                [],
            ]
        )

        result = await variable_manager.get_variables(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_variables_handles_missing_fields(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test handling variables with missing optional fields."""
        variables_data = [
            {"name": "var1", "expression": "1 in"},
            {"expression": "2 in"},  # Missing name
            {"name": "var2"},  # Missing expression
        ]

        onshape_client.get = AsyncMock(
            side_effect=[
                [{"id": sample_document_ids["element_id"], "elementType": "VARIABLESTUDIO"}],
                [{"variableStudioReference": None, "variables": variables_data}],
            ]
        )

        result = await variable_manager.get_variables(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
        )

        # Should handle missing fields gracefully with empty strings
        assert result[0].name == "var1"
        assert result[1].name == ""
        assert result[2].expression == ""

    @pytest.mark.asyncio
    async def test_get_variables_reads_part_studio_assign_variable_features(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test Part Studio variables are read from assignVariable features."""
        onshape_client.get = AsyncMock(
            side_effect=[
                [{"id": sample_document_ids["element_id"], "elementType": "PARTSTUDIO"}],
                {
                    "features": [
                        {
                            "featureType": "assignVariable",
                            "parameters": [
                                {"parameterId": "name", "value": "width"},
                                {"parameterId": "value", "expression": "240 mm"},
                            ],
                        },
                        {
                            "featureType": "extrude",
                            "parameters": [],
                        },
                    ]
                },
            ]
        )

        result = await variable_manager.get_variables(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
        )

        assert len(result) == 1
        assert result[0].name == "width"
        assert result[0].expression == "240 mm"

        call_args = onshape_client.get.call_args_list[1]
        path = call_args[0][0]
        assert "/partstudios/" in path
        assert path.endswith("/features")

    @pytest.mark.asyncio
    async def test_set_variable_with_description(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test setting a Variable Studio variable with description."""
        onshape_client.get = AsyncMock(
            return_value=[{"id": sample_document_ids["element_id"], "elementType": "VARIABLESTUDIO"}]
        )
        onshape_client.post = AsyncMock(return_value={"success": True})

        result = await variable_manager.set_variable(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
            "thickness",
            "0.25 in",
            "Material thickness",
        )

        assert result == {"success": True}

        # Verify data payload (sent as a list for the variables API)
        call_args = onshape_client.post.call_args
        data = call_args[1]["data"]
        assert isinstance(data, list)
        assert data[0]["name"] == "thickness"
        assert data[0]["expression"] == "0.25 in"
        assert data[0]["description"] == "Material thickness"

    @pytest.mark.asyncio
    async def test_set_variable_without_description(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test setting a Variable Studio variable without description."""
        onshape_client.get = AsyncMock(
            return_value=[{"id": sample_document_ids["element_id"], "elementType": "VARIABLESTUDIO"}]
        )
        onshape_client.post = AsyncMock(return_value={"success": True})

        await variable_manager.set_variable(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
            "depth",
            "1.5 in",
        )

        # Verify description is not in payload (sent as a list for the variables API)
        call_args = onshape_client.post.call_args
        data = call_args[1]["data"]
        assert isinstance(data, list)
        assert data[0]["name"] == "depth"
        assert data[0]["expression"] == "1.5 in"
        assert "description" not in data[0]

    @pytest.mark.asyncio
    async def test_set_variable_updates_existing(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test setting a Variable Studio variable remains supported."""
        onshape_client.get = AsyncMock(
            return_value=[{"id": sample_document_ids["element_id"], "elementType": "VARIABLESTUDIO"}]
        )
        onshape_client.post = AsyncMock(return_value={"updated": True})

        result = await variable_manager.set_variable(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
            "width",
            "15 in",
            "Updated width",
        )

        assert result == {"updated": True}

    @pytest.mark.asyncio
    async def test_set_variable_creates_part_studio_assign_variable_feature(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test creating a new Part Studio variable via feature creation."""
        onshape_client.get = AsyncMock(
            side_effect=[
                [{"id": sample_document_ids["element_id"], "elementType": "PARTSTUDIO"}],
                {"features": []},
            ]
        )
        onshape_client.post = AsyncMock(return_value={"featureState": {"featureStatus": "OK"}})

        result = await variable_manager.set_variable(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
            "base_length",
            "240 mm",
            "Base plate length",
        )

        assert result == {"featureState": {"featureStatus": "OK"}}

        call_args = onshape_client.post.call_args
        path = call_args[0][0]
        payload = call_args[1]["data"]
        assert "/partstudios/" in path
        assert path.endswith("/features")
        assert payload["btType"] == "BTFeatureDefinitionCall-1406"
        assert payload["feature"]["featureType"] == "assignVariable"
        assert payload["feature"]["parameters"][0]["value"] == "base_length"
        assert payload["feature"]["parameters"][1]["expression"] == "240 mm"

    @pytest.mark.asyncio
    async def test_set_variable_updates_existing_part_studio_assign_variable_feature(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test updating an existing Part Studio variable via feature update."""
        onshape_client.get = AsyncMock(
            side_effect=[
                [{"id": sample_document_ids["element_id"], "elementType": "PARTSTUDIO"}],
                {
                    "features": [
                        {
                            "featureId": "feat123",
                            "featureType": "assignVariable",
                            "parameters": [
                                {"parameterId": "name", "value": "base_length"},
                                {"parameterId": "value", "expression": "200 mm"},
                            ],
                        }
                    ]
                },
            ]
        )
        onshape_client.post = AsyncMock(return_value={"updated": True})

        result = await variable_manager.set_variable(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
            "base_length",
            "240 mm",
        )

        assert result == {"updated": True}

        call_args = onshape_client.post.call_args
        path = call_args[0][0]
        payload = call_args[1]["data"]
        assert path.endswith("/features/featureid/feat123")
        assert payload["feature"]["featureId"] == "feat123"
        assert payload["feature"]["parameters"][1]["expression"] == "240 mm"

    @pytest.mark.asyncio
    async def test_get_configuration_definition_success(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test getting configuration definition."""
        expected_config = {
            "configurationParameters": [
                {"parameterId": "param1", "type": "BTMConfigurationParameterEnum"}
            ]
        }

        onshape_client.get = AsyncMock(return_value=expected_config)

        result = await variable_manager.get_configuration_definition(
            sample_document_ids["document_id"],
            sample_document_ids["workspace_id"],
            sample_document_ids["element_id"],
        )

        assert result == expected_config

        # Verify path includes /configuration
        call_args = onshape_client.get.call_args
        path = call_args[0][0]
        assert "/configuration" in path

    @pytest.mark.asyncio
    async def test_variable_manager_api_error_handling(
        self, variable_manager, onshape_client, sample_document_ids
    ):
        """Test that API errors are propagated correctly."""
        onshape_client.get = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception) as exc_info:
            await variable_manager.get_variables(
                sample_document_ids["document_id"],
                sample_document_ids["workspace_id"],
                sample_document_ids["element_id"],
            )

        assert "Network error" in str(exc_info.value)
