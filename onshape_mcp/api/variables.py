"""Variable management for Onshape Part Studios and Variable Studios."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from .client import OnshapeClient


class Variable(BaseModel):
    """Represents a variable in an Onshape variable table."""

    name: str
    expression: str
    description: Optional[str] = None


class VariableManager:
    """Manager for Onshape variables.

    Part Studio variables are implemented as ``assignVariable`` features and must
    be created/updated through the Part Studio features API.

    Variable Studio variables are exposed through the dedicated ``/variables``
    endpoint.
    """

    def __init__(self, client: OnshapeClient):
        """Initialize the variable manager.

        Args:
            client: Onshape API client
        """
        self.client = client
        self._element_type_cache: Dict[str, str] = {}

    async def get_variables(
        self, document_id: str, workspace_id: str, element_id: str
    ) -> List[Variable]:
        """Get all variables from a Part Studio or Variable Studio.

        Args:
            document_id: Document ID
            workspace_id: Workspace ID
            element_id: Part Studio or Variable Studio element ID

        Returns:
            List of variables
        """
        element_type = await self._get_element_type(document_id, workspace_id, element_id)
        if element_type == "PARTSTUDIO":
            return await self._get_part_studio_variables(
                document_id, workspace_id, element_id
            )

        return await self._get_variables_endpoint(
            document_id, workspace_id, element_id
        )

    async def set_variable(
        self,
        document_id: str,
        workspace_id: str,
        element_id: str,
        name: str,
        expression: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set or update a variable.

        Args:
            document_id: Document ID
            workspace_id: Workspace ID
            element_id: Part Studio or Variable Studio element ID
            name: Variable name
            expression: Variable expression (e.g., "0.75 in")
            description: Optional variable description

        Returns:
            API response
        """
        element_type = await self._get_element_type(document_id, workspace_id, element_id)
        if element_type == "PARTSTUDIO":
            return await self._set_part_studio_variable(
                document_id,
                workspace_id,
                element_id,
                name,
                expression,
                description,
            )

        return await self._set_variable_studio_variable(
            document_id,
            workspace_id,
            element_id,
            name,
            expression,
            description,
        )

    async def get_configuration_definition(
        self, document_id: str, workspace_id: str, element_id: str
    ) -> Dict[str, Any]:
        """Get configuration definition for an element.

        Args:
            document_id: Document ID
            workspace_id: Workspace ID
            element_id: Element ID

        Returns:
            Configuration definition
        """
        path = f"/api/v6/elements/d/{document_id}/w/{workspace_id}/e/{element_id}/configuration"
        return await self.client.get(path)

    async def _get_element_type(
        self, document_id: str, workspace_id: str, element_id: str
    ) -> str:
        """Resolve and cache the element type for an element ID."""
        cache_key = f"{document_id}_{workspace_id}_{element_id}"
        if cache_key in self._element_type_cache:
            return self._element_type_cache[cache_key]

        path = f"/api/v6/documents/d/{document_id}/w/{workspace_id}/elements"
        elements = await self.client.get(path)
        for element in elements:
            if element.get("id") != element_id:
                continue
            element_type = self._normalize_element_type(
                element.get("elementType") or element.get("type") or ""
            )
            self._element_type_cache[cache_key] = element_type
            return element_type

        raise ValueError(f"Element '{element_id}' was not found in workspace '{workspace_id}'")

    def _normalize_element_type(self, raw_type: str) -> str:
        """Normalize element type strings from different API responses."""
        return raw_type.upper().replace(" ", "").replace("_", "")

    async def _get_variables_endpoint(
        self, document_id: str, workspace_id: str, element_id: str
    ) -> List[Variable]:
        """Read variables through the dedicated variables endpoint."""
        path = f"/api/v6/variables/d/{document_id}/w/{workspace_id}/e/{element_id}/variables"
        response = await self.client.get(path)
        return self._parse_variables_response(response)

    def _parse_variables_response(self, response: Any) -> List[Variable]:
        """Normalize variable endpoint responses into ``Variable`` objects."""
        if not isinstance(response, list):
            return []

        raw_variables: List[Dict[str, Any]] = []
        for item in response:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("variables"), list):
                raw_variables.extend(
                    var for var in item["variables"] if isinstance(var, dict)
                )
            else:
                raw_variables.append(item)

        return [
            Variable(
                name=var_data.get("name", ""),
                expression=self._extract_expression(var_data),
                description=var_data.get("description"),
            )
            for var_data in raw_variables
        ]

    async def _get_part_studio_variables(
        self, document_id: str, workspace_id: str, element_id: str
    ) -> List[Variable]:
        """Read Part Studio variables from assignVariable features."""
        path = f"/api/v9/partstudios/d/{document_id}/w/{workspace_id}/e/{element_id}/features"
        response = await self.client.get(path)
        features = response.get("features", [])

        variables: List[Variable] = []
        for feature in features:
            if feature.get("featureType") != "assignVariable":
                continue

            variable_name = ""
            expression = ""
            description = None

            for parameter in feature.get("parameters", []):
                parameter_id = parameter.get("parameterId")
                if parameter_id == "name":
                    variable_name = parameter.get("value", "")
                elif parameter_id == "value":
                    expression = self._extract_expression(parameter)
                elif parameter_id == "description":
                    description = parameter.get("value") or parameter.get("expression")

            variables.append(
                Variable(
                    name=variable_name,
                    expression=expression,
                    description=description,
                )
            )

        return variables

    async def _set_variable_studio_variable(
        self,
        document_id: str,
        workspace_id: str,
        element_id: str,
        name: str,
        expression: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write a variable to a Variable Studio via the variables endpoint."""
        path = f"/api/v6/variables/d/{document_id}/w/{workspace_id}/e/{element_id}/variables"
        data = [{"name": name, "expression": expression}]

        if description:
            data[0]["description"] = description

        return await self.client.post(path, data=data)

    async def _set_part_studio_variable(
        self,
        document_id: str,
        workspace_id: str,
        element_id: str,
        name: str,
        expression: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a Part Studio assignVariable feature."""
        path = f"/api/v9/partstudios/d/{document_id}/w/{workspace_id}/e/{element_id}/features"
        feature_list = await self.client.get(path)
        existing_feature = self._find_assign_variable_feature(
            feature_list.get("features", []), name
        )

        payload = self._build_assign_variable_payload(
            name=name,
            expression=expression,
            description=description,
            feature_id=existing_feature.get("featureId") if existing_feature else None,
        )

        if existing_feature:
            update_path = (
                f"/api/v9/partstudios/d/{document_id}/w/{workspace_id}/e/{element_id}"
                f"/features/featureid/{existing_feature['featureId']}"
            )
            return await self.client.post(update_path, data=payload)

        return await self.client.post(path, data=payload)

    def _find_assign_variable_feature(
        self, features: List[Dict[str, Any]], variable_name: str
    ) -> Optional[Dict[str, Any]]:
        """Find an existing assignVariable feature by variable name."""
        for feature in features:
            if feature.get("featureType") != "assignVariable":
                continue

            for parameter in feature.get("parameters", []):
                if (
                    parameter.get("parameterId") == "name"
                    and parameter.get("value") == variable_name
                ):
                    return feature

        return None

    def _build_assign_variable_payload(
        self,
        name: str,
        expression: str,
        description: Optional[str] = None,
        feature_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build an assignVariable feature payload for a Part Studio."""
        feature: Dict[str, Any] = {
            "btType": "BTMFeature-134",
            "featureType": "assignVariable",
            "name": f"#{name} = {expression}",
            "namespace": "",
            "suppressed": False,
            "returnAfterSubfeatures": False,
            "subFeatures": [],
            "parameters": [
                {
                    "btType": "BTMParameterString-149",
                    "parameterId": "name",
                    "parameterName": "",
                    "libraryRelationType": "NONE",
                    "value": name,
                },
                {
                    "btType": "BTMParameterQuantity-147",
                    "parameterId": "value",
                    "parameterName": "",
                    "libraryRelationType": "NONE",
                    "expression": expression,
                    "isInteger": False,
                    "value": 0.0,
                    "units": "",
                },
            ],
        }

        # Part Studio assignVariable does not consistently expose description as
        # a supported feature parameter. Keep the signature for compatibility,
        # but only persist parameters that the feature endpoint accepts reliably.
        if feature_id:
            feature["featureId"] = feature_id

        return {"btType": "BTFeatureDefinitionCall-1406", "feature": feature}

    def _extract_expression(self, data: Dict[str, Any]) -> str:
        """Read an expression from variables or feature parameters."""
        if data.get("expression"):
            return data["expression"]

        value = data.get("value")
        units = data.get("units", "")
        if value is None:
            return ""
        if units:
            return f"{value} {units}".strip()
        return str(value)
