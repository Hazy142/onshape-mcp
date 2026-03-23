# Onshape Workflows

## Overview

This document consolidates the relevant Onshape workflows for this repository.
It is intended as the operational reference for future modeling, drawing, export,
and debugging work.

Status note:
- Verified against official Onshape API documentation and live API behavior in
  this workspace on March 23, 2026.

Core repo entry points:
- `onshape_mcp/api/client.py`
- `onshape_mcp/api/documents.py`
- `onshape_mcp/api/partstudio.py`
- `onshape_mcp/api/variables.py`
- `onshape_mcp/builders/sketch.py`
- `onshape_mcp/builders/extrude.py`
- `onshape_mcp/builders/thicken.py`

## Workflow 1: Authentication and Base URL

Use API key authentication with:
- `ONSHAPE_ACCESS_KEY`
- `ONSHAPE_SECRET_KEY`
- `ONSHAPE_BASE_URL`

For standard accounts:
- `https://cad.onshape.com`

For enterprise stacks:
- `https://<company>.onshape.com`

Rules:
- `ONSHAPE_BASE_URL` must be the stack root, not a document URL.
- API keys are stack-bound. A key created on one stack will fail on another.
- OAuth is not needed for this local MCP workflow.

## Workflow 2: Document, Workspace, and Element Resolution

Resolve the target context in this order:
1. List or search documents.
2. Resolve the workspace.
3. Resolve elements in the workspace.
4. Pick the specific `PARTSTUDIO`, `ASSEMBLY`, `DRAWING`, or `VARIABLESTUDIO`.

Primary endpoints:
- `GET /api/v10/documents`
- `GET /api/v10/documents/d/{did}/w/{wid}/elements`
- `GET /api/v9/partstudios/d/{did}/w/{wid}/e/{eid}/features`

Why this matters:
- Most failures in live runs are wrong `eid`, wrong stack, or wrong element type.

## Workflow 3: Part Studio Modeling

Recommended sequence:
1. Resolve standard plane IDs.
2. Create a sketch.
3. Create a solid feature from the sketch.
4. Read parts and bounding boxes to verify geometry.

Plane IDs used in this repo:
- Front: `JCC`
- Top: `JDC`
- Right: `JEC`

Verification endpoints:
- `GET /api/v9/parts/d/{did}/w/{wid}/e/{eid}`
- `GET /api/v6/parts/d/{did}/w/{wid}/e/{eid}/partid/{pid}/boundingboxes`

## Workflow 4: Sketch Creation

Current reliable sketch path in this repo:
- Build `BTMSketch-151` as the top-level feature object inside the request body.
- Use `featureType = "newSketch"`.
- Use explicit sketch entities and constraints.

Confirmed working pattern:
- `create_sketch_rectangle`
- `create_sketch_circle`
- `create_sketch_line`
- `create_sketch_arc`

Current repo behavior:
- `onshape_mcp/builders/sketch.py` can create rectangle sketches that Onshape accepts.
- The resulting sketch feature may still report `WARNING` while remaining usable for downstream extrudes.

Important practical point:
- A sketch returning `WARNING` is not automatically fatal.
- The real test is whether a solid feature can consume the region and whether the resulting part is correct.

## Workflow 5: Extrude Creation

This was a confirmed live fix.

Reliable extrude payload must include:
- `bodyType = SOLID`
- `operationType = NEW|ADD|REMOVE|INTERSECT`
- `entities` with `BTMIndividualSketchRegionQuery-140`
- `endBound = BLIND`
- `depth`

Minimal working shape:

```json
{
  "btType": "BTFeatureDefinitionCall-1406",
  "feature": {
    "btType": "BTMFeature-134",
    "featureType": "extrude",
    "name": "Extrude 1",
    "parameters": [
      {
        "btType": "BTMParameterEnum-145",
        "enumName": "ExtendedToolBodyType",
        "value": "SOLID",
        "parameterId": "bodyType"
      },
      {
        "btType": "BTMParameterEnum-145",
        "enumName": "NewBodyOperationType",
        "value": "NEW",
        "parameterId": "operationType"
      },
      {
        "btType": "BTMParameterQueryList-148",
        "parameterId": "entities",
        "queries": [
          {
            "btType": "BTMIndividualSketchRegionQuery-140",
            "featureId": "<sketchFeatureId>"
          }
        ]
      },
      {
        "btType": "BTMParameterEnum-145",
        "enumName": "BoundingType",
        "value": "BLIND",
        "parameterId": "endBound"
      },
      {
        "btType": "BTMParameterQuantity-147",
        "parameterId": "depth",
        "expression": "10 mm"
      }
    ]
  }
}
```

Confirmed live result:
- Literal-depth extrude works.

Current limitation:
- Variable-driven extrude depth using `expression: "#variable"` still fails live with:
  `Parameter depth ... does not match its feature spec`

Practical consequence:
- Use literal depth for stable live modeling until the exact variable-depth feature format is recovered from a UI-authored reference.

## Workflow 6: Thicken Creation

Current state:
- `thicken` is not the preferred base workflow in this repo.
- Live tests were less reliable than the corrected extrude path.

Recommendation:
- Prefer `sketch -> extrude` for base solids.
- Revisit `thicken` only when a specific geometry requires it.

## Workflow 7: Variables in Part Studios

This repo now distinguishes two paths:
- Part Studio variables via `assignVariable` features
- Variable Studio variables via `/variables`

Current implementation:
- `onshape_mcp/api/variables.py`

Part Studio path:
- Read variables by scanning `assignVariable` features from `/features`
- Create/update variables by posting `assignVariable` features through `/features`

Confirmed live behavior in this workspace:
- Create/update/readback of Part Studio variables works mechanically.
- The features usually return `WARNING`.
- In tested Part Studios, these variables did not regenerate sketch-driven geometry.

Operational conclusion:
- Treat Part Studio variable authoring as partially working.
- Do not rely on it yet for production parametric regeneration.

## Workflow 8: Variables in Variable Studios

Element type:
- `VARIABLESTUDIO`

Read path:
- `GET /api/v6/variables/d/{did}/w/{wid}/e/{eid}/variables`

Confirmed live behavior:
- Reading from an existing Variable Studio works.

Current blocker:
- Writing to the Variable Studio with the obvious array payload still returned `500` in live tests on March 23, 2026.

Operational conclusion:
- Variable Studio is present and detectable.
- Variable Studio write support in this repo is not yet reliable enough to use as the primary parametric path.

## Workflow 9: Assemblies

Use assemblies only after part geometry is stable.

Recommended sequence:
1. Build or import parts in Part Studios.
2. Create an Assembly tab if needed.
3. Insert instances.
4. Position instances or create mates.
5. Query final assembly definition and feature state.

Key endpoints:
- `POST /api/v9/assemblies/d/{did}/w/{wid}`
- `POST /api/v9/assemblies/d/{did}/w/{wid}/e/{eid}/instances`
- `GET /api/v9/assemblies/d/{did}/w/{wid}/e/{eid}`
- `POST /api/v9/assemblies/d/{did}/w/{wid}/e/{eid}/modify`

Use this when:
- The machine moves as an assembly.
- Mates and positional behavior matter more than single-Part-Studio construction.

## Workflow 10: Drawings

For drawings, use a separate bridge layer, not `onshape-mcp` directly.

Preferred stack in this workspace:
- `onshape-mcp` for geometry and assemblies
- `onshape-drawing-bridge` for drawing creation and export

Confirmed API capabilities:
- `createDrawing`
- `modifyDrawing`
- drawing export workflows

Practical note:
- Keep drawings as a second stage after part and assembly stabilization.
- Avoid coupling drawing generation to incomplete parametric modeling logic.

## Workflow 11: Export

Use export only after geometry is verified.

Supported repo paths:
- Part Studio export
- Assembly export

Typical export targets:
- STL
- STEP
- PARASOLID
- GLTF
- OBJ

Verification before export:
- feature states are acceptable
- part count is correct
- bounding boxes match expected scale

## Workflow 12: Debugging Sequence

When a live Onshape operation fails, use this order:
1. Verify stack root and auth.
2. Verify `did`, `wid`, `eid`.
3. Verify element type.
4. Read the full feature list from the target Part Studio.
5. Compare the outgoing payload to the feature structure returned by Onshape UI-authored features.
6. Confirm result with `get_parts` and bounding box, not just feature creation response.

Useful checks:
- `featureStates`
- part count
- bounding box dimensions
- actual persisted feature JSON after Onshape rewrites the request

Important lesson from this repo:
- A request can return a created feature and still not produce the intended parametric behavior.

## Workflow 13: Recommended Order for This Repository

Use this order unless there is a strong reason not to:
1. Authenticate and resolve stack.
2. Resolve document/workspace/element IDs.
3. Create literal sketches and literal extrudes first.
4. Validate with parts and bounding boxes.
5. Only then introduce variable-driven behavior.
6. Build assemblies after part geometry is stable.
7. Build drawings after assemblies are stable.
8. Export last.

Reason:
- This minimizes false positives from partially working variable flows.

## Current Known Limitations

Confirmed as of March 23, 2026:
- Part Studio `assignVariable` features can be created and updated, but did not regenerate tested geometry in this workspace.
- Variable Studio write path still failed live.
- Variable-driven extrude depth was rejected by the live feature spec.
- Literal extrude is reliable and should be treated as the current production-safe path.

## Immediate Use Rules

Use these rules in the next modeling steps:
- Build machine parts with literal extrudes unless a UI-authored variable reference is copied and verified.
- Keep variable names and intended design intent documented even when geometry is still fixed.
- Use live bounding box checks after every major solid feature.
- Do not trust `WARNING` alone as a blocker; trust the resulting geometry.

## Sources

- Official feature access docs: https://onshape-public.github.io/docs/api-adv/featureaccess/
- Official documents docs: https://onshape-public.github.io/docs/api-adv/documents/
- Official drawings docs: https://onshape-public.github.io/docs/api-adv/drawings/
- Official auth docs: https://onshape-public.github.io/docs/auth/
