# M7U4 — From IFC to Graph: Data Quality Analysis of the buildingSMART Duplex Apartment Model, with Cross-Model Validation against an MEP Services Dataset

**Module:** M7 — IFC Data Processing, Analysis and Schema Implementation
**Unit:** M7U4 — From IFC to Dataset / Structuring and Validating Data / From Data to Insight
**Programme:** Masters in AI in Architecture and Construction, Zigurat Global Institute of Technology
**Author:** Shane Haines
**Date:** June 2026

---

## Reading guide for examiners

This submission maps to the rubric as follows:

- **Graph model definition (25%)** — §2, with schema diagram embedded
- **IFC → graph transformation process (20%)** — §3, with toolchain and 8-stage ETL description
- **Cypher queries (25%)** — §4, with standalone `.cypher` files in `queries/` (Q1–Q8) and `queries/hvac/` (Q1–Q11)
- **Interpretation of results (15%)** — §5, with cross-model comparative findings
- **Documentation clarity (15%)** — repository layout in §6, reproduction steps in §7

CSV exports for every query are in `results/` (Duplex set) and `results/hvac/` (HVAC set). Seven Neo4j screenshots are in `screenshots/`.

§4.1 adds a cross-model validation against an MEP services dataset (NBU MedicalClinic HVAC) and three Services-BIM-specific queries (Q9–Q11). This is beyond the minimum requirements; the eight required queries (Q1–Q8) stand on their own in §4.

### Why two models?

The assignment brief requires one IFC model and eight queries. This submission delivers two models and eleven queries. The reasoning:

- **Professional relevance.** As a practising Services BIM Consultant, validating a data-quality methodology against an architectural model alone would leave the central professional question unanswered: does the approach hold up for the discipline I actually deliver?
- **Methodological strength.** A single-model analysis cannot distinguish "the model is good" from "my queries don't fire." Running the same eight queries across two contrasting datasets — architectural and MEP — surfaces failure modes that one model alone would hide. Q1 (elements without property sets) inverts between the two datasets: 41 in the Duplex, 0 in the HVAC. A single-model audit would miss exactly this kind of finding.
- **Risk-managed scope.** The eight required queries (Q1–Q8) against the Duplex Apartment model in §4 stand alone as a complete minimum-requirements submission. The HVAC cross-validation in §4.1 and the three MEP-specific queries (Q9–Q11) are additive, not a replacement.

---

## 1. Executive summary

This submission demonstrates a complete IFC-to-graph workflow validated against two contrasting buildingSMART-class IFC datasets:

1. The **Duplex Apartment** reference model (`Duplex_A_20110907.ifc`, IFC2x3, CC-BY-4.0) — a 268-element architectural model used to develop and verify the schema and queries.
2. The **NBU MedicalClinic HVAC** model (`NBU_MedicalClinic_Eng-HVAC.ifc`, IFC2x3, TIB DURAARK dataset) — a 3,704-element MEP services model used to validate that the schema, the eight standard data-quality queries, and three new Services-BIM-specific queries (Q9–Q11) generalise beyond architectural data.

Each model is transformed into a Neo4j property graph using `ifcopenshell` and the official Neo4j Python driver. Both datasets live as separate Neo4j databases on the same instance (`neo4j` and `hvac` respectively), with a shared loader module that scales via batched `MERGE` to 190,000+ nodes.

The two graphs together total **209,867 nodes and 216,364 relationships**. Across the eleven queries the comparison surfaces a clear pattern: well-curated public IFCs pass identity checks (uniqueness, named spaces, fire-rated doors where applicable) but consistently fail on completeness and validity — and **MEP services models fail in ways that are invisible to a generic architectural quality audit**, which is the central argument for adopting Services-BIM-specific tooling.

This submission is the work of a practising Services BIM Consultant; the cross-model validation is included because restricting analysis to an architectural reference model alone would leave the central professional question — does the approach work for the discipline I actually deliver? — unanswered.

---

## 2. Graph model — definition and rationale

![M7U4 graph schema](docs/graph_schema.svg)

The graph schema is designed around four principles drawn directly from the lecture material:

1. **GUID as identity** — every IFC entity that has a `GlobalId` becomes a node keyed by that GUID, enforced by a uniqueness constraint (`element_globalid`). This makes the graph robust to re-loads and aligns with Evelio's statement in Session 1 that "in Neo4j, the GUID will usually become the node identity."
2. **Relationships as first-class citizens** — IFC's relational entities (`IfcRelContainedInSpatialStructure`, `IfcRelDefinesByProperties`, `IfcRelDefinesByType`, `IfcRelAggregates`, `IfcRelAssociatesMaterial`) are translated into named relationships, not collapsed into element properties. This preserves the graph's traversability.
3. **Property sets as nodes, not attributes** — instead of flattening every property onto its host element, `:PropertySet` and `:Property` are modelled as their own nodes connected via `[:HAS_PSET]` and `[:HAS_PROPERTY]`. This is the critical design decision that enables Q1 ("elements with no property sets"), Q5 ("properties with empty values") and Q6 ("incompleteness by category") to be expressed as simple Cypher patterns.
4. **Dual labelling per IFC class** — every element carries both the generic `:Element` label *and* its specific IFC class as a secondary label (e.g. `:Element:IfcDoor`, `:Element:IfcFlowTerminal`). Generic checks query `:Element`; class-specific checks query `:IfcDoor` or `:IfcFlowTerminal`. This avoids the choice between a flat schema (lossy) and a fully normalised schema (slow to query).

### 2.1 Node labels

| Label                                 | IFC source                        | Carried properties                                                 |
| ------------------------------------- | --------------------------------- | ------------------------------------------------------------------ |
| `:Project`                            | `IfcProject`                      | `GlobalId`, `Name`, `LongName`, `Description`                      |
| `:Site`                               | `IfcSite`                         | `GlobalId`, `Name`, `LongName`, `Description`                      |
| `:Building`                           | `IfcBuilding`                     | `GlobalId`, `Name`, `LongName`, `Description`                      |
| `:Storey`                             | `IfcBuildingStorey`               | `GlobalId`, `Name`, `LongName`, `Description`                      |
| `:Space`                              | `IfcSpace`                        | `GlobalId`, `Name`, `LongName`, `Description`                      |
| `:Element` (+ secondary `:IfcXxx`)    | `IfcElement` and subtypes         | `GlobalId`, `IfcClass`, `Name`, `ObjectType`, `Tag`, `Description` |
| `:Type`                               | `IfcTypeObject`                   | `GlobalId`, `IfcClass`, `Name`                                     |
| `:PropertySet`                        | `IfcPropertySet` instance         | `pset_id`, `Name`                                                  |
| `:Property`                           | individual property within a Pset | `prop_id`, `Name`, `Value`, `DataType`, `IsEmpty`                  |
| `:Material`                           | `IfcMaterial`                     | `Name`                                                             |
| `:DistributionPort` *(MEP extension)* | `IfcDistributionPort`             | `GlobalId`, `Name`, `FlowDirection`                                |

### 2.2 Relationship types

| Relationship                        | Direction                             | IFC source                                              |
| ----------------------------------- | ------------------------------------- | ------------------------------------------------------- |
| `[:CONTAINS]`                       | spatial parent → child                | `IfcRelAggregates`, `IfcRelContainedInSpatialStructure` |
| `[:HAS_PSET]`                       | element → property set                | `IfcRelDefinesByProperties`                             |
| `[:HAS_PROPERTY]`                   | property set → property               | derived from `IfcPropertySet.HasProperties`             |
| `[:DEFINED_BY]`                     | element → type                        | `IfcRelDefinesByType`                                   |
| `[:MADE_OF]`                        | element → material                    | `IfcRelAssociatesMaterial`                              |
| `[:HAS_PORT]` *(MEP extension)*     | element → distribution port           | `IfcRelConnectsPortToElement`                           |
| `[:CONNECTED_TO]` *(MEP extension)* | distribution port → distribution port | `IfcRelConnectsPorts`                                   |

The `:DistributionPort` node label and the `[:HAS_PORT]` / `[:CONNECTED_TO]` relationships are MEP-specific schema extensions activated automatically by the loader when the source IFC contains `IfcDistributionPort` entities. Architectural-only models incur no cost from this extension; the HVAC model gains a complete system-topology layer.

### 2.3 Loaded graphs at a glance

The two databases on the same Neo4j instance:

| Aspect                  | Duplex (`neo4j` DB) | HVAC (`hvac` DB) |
| ----------------------- | ------------------- | ---------------- |
| Nodes (total)           | 16,178              | 193,689          |
| Relationships (total)   | 16,102              | 200,262          |
| `:Element`              | 268                 | 3,704            |
| `:PropertySet`          | 2,388               | 33,053           |
| `:Property`             | 13,455              | 148,447          |
| `:DistributionPort`     | 0 *(n/a)*           | 7,390            |
| `:Storey`               | 4                   | 4                |
| `:Space`                | 21                  | 263              |
| `:HAS_PROPERTY`         | 13,455              | 148,447          |
| `:HAS_PSET`             | 2,215               | 33,053           |
| `:CONTAINS`             | 234                 | 3,973            |
| `:HAS_PORT` *(MEP)*     | 0                   | 7,390            |
| `:CONNECTED_TO` *(MEP)* | 0                   | 3,695            |

See `screenshots/00_graph_overview.png` (Duplex schema panel) and `screenshots/03_hvac_database_overview.png` (HVAC schema panel) for the Neo4j-rendered views.

---

## 3. IFC-to-graph transformation process

### 3.1 Toolchain

| Stage               | Tool                                    | Version    |
| ------------------- | --------------------------------------- | ---------- |
| IFC parsing         | `ifcopenshell`                          | latest pip |
| Property extraction | `ifcopenshell.util.element.get_psets()` | bundled    |
| Graph database      | Neo4j (via Neo4j Desktop 2)             | 2026.05.0  |
| Driver              | `neo4j` Python driver                   | latest pip |
| Environment         | Python 3 venv, Jupyter Notebook         | —          |
| Credentials         | `.env` via `python-dotenv`              | —          |

This is the **Extract → Transform → Load → Query** pipeline exactly as laid out in Session 1 (Slide: *"The ETL pipeline in construction"*), realised in code rather than diagram.

### 3.2 ETL stages

1. **Open the IFC** with `ifcopenshell.open()`.
2. **Connect to Neo4j** using credentials loaded from `.env` (`neo4j://127.0.0.1:7687`, user `neo4j`).
3. **Wipe and constrain** — clear the database with `MATCH (n) DETACH DELETE n`, create the GlobalId uniqueness constraint, and create backing indexes on every keyed property (`PropertySet.pset_id`, `Property.prop_id`, etc.). The indexes are critical: without them, `MERGE` on 148k properties is quadratic and the HVAC load takes hours; with them it takes 17 minutes.
4. **Load the spatial hierarchy** — Project → Site → Building → Storey → Space, traversed via `IfcRelAggregates`.
5. **Load elements** — `ifc_file.by_type("IfcElement")` returns every physical element. Each is created with dual labelling (`:Element:IfcXxx`). Storey containment is then resolved via `IfcRelContainedInSpatialStructure`.
6. **Load property sets and properties** in batches of 500 via `UNWIND $batch AS row MERGE ...`. Each property carries a pre-computed `IsEmpty` flag derived from null or whitespace-only values, moving cost from query time to load time.
7. **Load types and materials** — `IfcRelDefinesByType` and `IfcRelAssociatesMaterial` are walked, with elements linked to their type and material nodes.
8. **Load distribution ports (MEP-only)** — if the IFC contains `IfcDistributionPort` entities, create `:DistributionPort` nodes with `[:HAS_PORT]` and `[:CONNECTED_TO]` edges.
9. **Verify** — node and relationship counts are printed for every label and type.

The ETL is **idempotent**: re-running the notebook wipes the database first, so the graph can be rebuilt from scratch at any point without orphaned data.

The implementation lives in `notebooks/loader.py` as an `IFCGraphLoader` class. Both the Duplex notebook (`01_extract_and_load.ipynb`) and the HVAC notebook (`03_extract_and_load_hvac.ipynb`) instantiate it with the appropriate `database=` parameter so each graph populates its own Neo4j database without contaminating the other.

---

## 4. Data quality queries

Eleven queries are executed against each graph (eight standard plus three MEP-specific). Each query is stored as a standalone file in `queries/` (Duplex) and `queries/hvac/` (HVAC), results are exported to `results/` and `results/hvac/` respectively, and findings are summarised in §5.

### Q1 — Elements with no property sets (Completeness)

```cypher
MATCH (e:Element)
WHERE NOT (e)-[:HAS_PSET]->()
RETURN e.GlobalId AS GlobalId, e.IfcClass AS IfcClass,
       e.Name AS Name, e.Tag AS Tag
ORDER BY e.IfcClass, e.Name
```

- **Dimension:** Completeness
- **Returns:** every element with zero outgoing `[:HAS_PSET]` relationships
- **Interpretation:** an element with no property sets is a geometric placeholder with no semantic metadata. It cannot support cost estimation, energy analysis, fire compliance or facility management handover.

### Q2 — Doors without a FireRating (Completeness / compliance-critical)

```cypher
MATCH (d:Element:IfcDoor)
OPTIONAL MATCH (d)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property {Name: 'FireRating'})
WITH d, p
WHERE p IS NULL OR p.IsEmpty = true
RETURN d.GlobalId AS GlobalId, d.Name AS DoorName, d.Tag AS Tag,
       CASE WHEN p IS NULL THEN 'Missing' ELSE 'Empty' END AS FireRatingStatus,
       p.Value AS RawValue
ORDER BY FireRatingStatus, d.Name
```

- **Dimension:** Completeness (compliance-critical)
- **Returns:** any door where `FireRating` is absent or empty
- **Interpretation:** doors without fire rating data fail Building Regulations Part B (UK) and equivalent compartmentation checks under the Building Safety Act 2022 Golden Thread.

### Q3 — Elements not assigned to any storey (Consistency / spatial integrity)

```cypher
MATCH (e:Element)
WHERE NOT EXISTS { MATCH (:Storey)-[:CONTAINS]->(e) }
RETURN e.GlobalId AS GlobalId, e.IfcClass AS IfcClass,
       e.Name AS Name, e.Tag AS Tag
ORDER BY e.IfcClass
```

- **Dimension:** Consistency (spatial integrity)
- **Returns:** every element with no incoming `[:CONTAINS]` from a `:Storey`
- **Interpretation:** orphaned elements break automated quantity take-offs, energy simulations and storey-based dashboards. Note: `IfcOpeningElement` instances are spatially "voided" into their host wall via `IfcRelVoidsElement` rather than contained by a storey — they appear as legitimate false positives, illustrating that consistency rules must be class-aware.

### Q4 — Spaces with no name or number (Completeness / identity)

```cypher
MATCH (s:Space)
WHERE s.Name IS NULL OR trim(s.Name) = ''
   OR s.LongName IS NULL OR trim(s.LongName) = ''
RETURN s.GlobalId AS GlobalId,
       coalesce(s.Name, '<MISSING>') AS RoomNumber,
       coalesce(s.LongName, '<MISSING>') AS RoomName,
       s.Description AS Description
ORDER BY s.GlobalId
```

- **Dimension:** Completeness (identity)
- **Returns:** any `:Space` whose `Name` or `LongName` is null or whitespace-only
- **Interpretation:** a space without identity cannot be referenced in area schedules, FM software or COBie handover.

### Q5 — Properties present but empty (Completeness / illusion of structure)

```cypher
MATCH (e:Element)-[:HAS_PSET]->(ps:PropertySet)-[:HAS_PROPERTY]->(p:Property)
WHERE p.IsEmpty = true
RETURN e.GlobalId AS ElementGlobalId, e.IfcClass AS IfcClass,
       e.Name AS ElementName, ps.Name AS PropertySet,
       p.Name AS PropertyName, p.DataType AS DataType
ORDER BY e.IfcClass, ps.Name, p.Name
```

- **Dimension:** Completeness — the "illusion of structured data" failure mode
- **Returns:** every property whose `Value` is null or whitespace-only
- **Interpretation:** an empty property is worse than a missing one because automated audits that count Psets see them as present.

### Q6 — Incompleteness ranked by IFC category (Completeness, aggregated)

```cypher
MATCH (e:Element)
OPTIONAL MATCH (e)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property)
WITH e.IfcClass AS Category, e, p
WITH Category,
     count(DISTINCT e) AS TotalElements,
     count(p) AS TotalProperties,
     sum(CASE WHEN p.IsEmpty = true THEN 1 ELSE 0 END) AS EmptyProperties
RETURN Category, TotalElements, TotalProperties, EmptyProperties,
       CASE WHEN TotalProperties = 0 THEN 0.0
            ELSE round(toFloat(EmptyProperties) / TotalProperties, 3)
       END AS EmptyRatio
ORDER BY EmptyProperties DESC, EmptyRatio DESC
```

- **Dimension:** Completeness, aggregated for prioritisation
- **Returns:** for each IFC category, total elements, total properties, empty properties, and the empty ratio
- **Interpretation:** turns Q1 and Q5 into a remediation backlog.

### Q7 — Duplicate identifiers and names (Uniqueness)

Two sub-queries on GlobalId uniqueness (Q7a) and Name+IfcClass uniqueness (Q7b). See `queries/Q7a_*.cypher` and `queries/Q7b_*.cypher`.

### Q8 — Property values outside the permitted set (Validity)

Tests `FireRating` and `IsExternal` against controlled vocabularies. See `queries/Q8_*.cypher`.

---

## 4.1 Cross-model validation against an MEP services dataset

The eight queries above were developed against the architectural Duplex Apartment model. To verify the approach generalises beyond architecture — and to align the analysis with the author's professional domain as a Services BIM Consultant — the schema and queries were re-applied to a real HVAC services model.

### 4.1.1 The HVAC dataset

The **NBU_MedicalClinic_Eng-HVAC.ifc** model is part of the **DURAARK** project's open dataset, hosted by the **Technische Informationsbibliothek (TIB) Hannover**:

```
https://tib.eu/data/duraark/BuildingData/01_IFC/NBU_MedicalClinic_ifc.zip
```

The zip contains five discipline-separated IFC files from the same medical clinic project (architectural, MEP, HVAC, electrical, structural). The HVAC file alone is 27 MB and contains 3,704 services elements across six MEP IFC classes:

| IFC class                 | Count | Role                               |
| ------------------------- | ----- | ---------------------------------- |
| IfcFlowFitting            | 1,590 | Duct fittings, transitions, elbows |
| IfcFlowSegment            | 1,548 | Duct runs                          |
| IfcFlowTerminal           | 440   | Air diffusers, grilles, registers  |
| IfcFlowController         | 115   | Dampers, VAVs, valves              |
| IfcFlowMovingDevice       | 8     | Fans, AHUs                         |
| IfcEnergyConversionDevice | 3     | Heat-exchange equipment            |

The model also contains **7,390 IfcDistributionPort instances** with **3,695 IfcRelConnectsPorts** relationships — that is, every duct end is captured as a port and the port-to-port connections define the actual flow topology of the HVAC system.

### 4.1.2 Schema extensions for MEP

To handle this content, the loader was extended with three additions, activated automatically when the source IFC contains `IfcDistributionPort` entities:

- A new node label `:DistributionPort` with `GlobalId`, `Name` and `FlowDirection` properties
- A `[:HAS_PORT]` relationship from `:Element` to its `:DistributionPort` nodes (one element typically has 2 ports — inlet and outlet)
- A `[:CONNECTED_TO]` relationship between connected `:DistributionPort` nodes, capturing the system topology

Architectural models are unaffected — when an IFC contains no `IfcDistributionPort` entities the extension is a no-op.

`screenshots/05_hvac_system_topology.png` shows a connected duct chain rendered from the HVAC graph: 96 nodes (46 elements + 50 ports) linked by 75 relationships (50 `HAS_PORT` + 25 `CONNECTED_TO`). Walking from an air terminal to its upstream AHU through the port topology is now a single Cypher traversal.

### 4.1.3 MEP-specific data quality queries

Three new queries were added specifically for Services BIM data validation. These would not surface meaningful results in an architectural model — they target patterns unique to MEP discipline.

#### Q9 — Flow terminals without a flow-rate property (Completeness, MEP)

```cypher
MATCH (e:Element:IfcFlowTerminal)
WHERE NOT EXISTS {
  MATCH (e)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property)
  WHERE p.IsEmpty = false
    AND p.Name IN ['NominalAirflowRate','AirflowRate','FlowRate','NominalFlowRate']
}
RETURN e.GlobalId AS GlobalId, e.IfcClass AS IfcClass,
       e.Name AS Name, e.Tag AS Tag
ORDER BY e.Name
```

- **Dimension:** Completeness (Services-BIM-specific)
- **Returns:** every flow terminal lacking a populated airflow-rate property
- **Interpretation:** an air diffuser without a flow rate cannot be used in commissioning, balancing reports or energy simulations.

#### Q10 — Flow elements without IfcDistributionSystem assignment (Consistency, MEP)

```cypher
MATCH (e:Element)
WHERE e.IfcClass IN ['IfcFlowSegment','IfcFlowFitting','IfcFlowTerminal',
                     'IfcFlowController','IfcFlowMovingDevice',
                     'IfcEnergyConversionDevice']
RETURN e.IfcClass AS IfcClass, count(*) AS UnassignedCount
ORDER BY UnassignedCount DESC
```

- **Dimension:** Consistency (Services-BIM-specific)
- **Returns:** flow element counts per class — the HVAC model contains zero `IfcDistributionSystem` instances, so every flow element is unassigned by definition
- **Interpretation:** a coordinated MEP model should group elements into named distribution systems (Supply Air, Return Air, Exhaust, Chilled Water, etc.). Without that grouping, system-based maintenance and commissioning workflows fail.

#### Q11 — Flow segments missing nominal diameter (Completeness, MEP)

```cypher
MATCH (e:Element)
WHERE e.IfcClass IN ['IfcFlowSegment','IfcFlowFitting']
  AND NOT EXISTS {
    MATCH (e)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property)
    WHERE p.IsEmpty = false
      AND p.Name IN ['NominalDiameter','OuterDiameter','InnerDiameter',
                     'NominalWidth','NominalHeight','Width','Height']
  }
RETURN e.IfcClass AS IfcClass, count(*) AS SegmentsMissingDiameter
ORDER BY SegmentsMissingDiameter DESC
```

- **Dimension:** Completeness (Services-BIM-specific)
- **Returns:** counts of flow segments/fittings missing dimensional properties
- **Interpretation:** without dimensional data, pressure-drop calculations, flow-balance analysis and bills of quantities cannot be derived from the model.

### 4.1.4 Comparative findings

Eleven queries × two models = 22 result sets, summarised below.

| #   | Question                                 | Dimension                 | Duplex (Architectural)   | HVAC (Services)                                      |
| --- | ---------------------------------------- | ------------------------- | ------------------------ | ---------------------------------------------------- |
| Q1  | Elements with no property sets           | Completeness              | **41** (≈15% of 268)     | **0**                                                |
| Q2  | Doors missing FireRating                 | Completeness (compliance) | **0**                    | **0** *(no doors in this discipline file)*           |
| Q3  | Elements not in any storey               | Consistency (spatial)     | **122** (≈46%)           | **2,114** (≈57%)                                     |
| Q4  | Spaces missing name/number               | Completeness (identity)   | **0**                    | **0**                                                |
| Q5  | Properties with empty values             | Completeness              | **452** (3.4% of 13,455) | **10,729** (7.2% of 148,447)                         |
| Q6  | Incompleteness by category               | Completeness (agg.)       | 15 categories            | 6 categories                                         |
| Q7a | Duplicate GlobalIds                      | Uniqueness                | **0**                    | **0**                                                |
| Q7b | Shared Names within class                | Uniqueness                | **0**                    | **0**                                                |
| Q8  | Values outside permitted set             | Validity                  | **62**                   | **0** *(no FireRating / IsExternal in scope)*        |
| Q9  | Flow terminals missing flow rate         | Completeness (MEP)        | n/a                      | **440** (100% of all flow terminals)                 |
| Q10 | Flow elements without DistributionSystem | Consistency (MEP)         | n/a                      | **3,704** (100% of flow elements; 0 systems defined) |
| Q11 | Flow segments missing diameter           | Completeness (MEP)        | n/a                      | 2 classes with missing dimensions                    |

### 4.1.5 Interpretation

Three patterns stand out from the comparison.

**Identity is universally strong.** Both models pass Q1, Q4 and Q7 — every space named, every GlobalId unique, no name collisions. This reflects the public-curation effort behind both reference datasets; real-world IFCs rarely look this clean.

**Spatial consistency is universally fragile.** Q3 fails in both models — 46% of architectural elements and 57% of services elements are not assigned to a storey. While part of the architectural figure is the legitimate `IfcOpeningElement` false-positive class, no equivalent excuse exists for HVAC. The pattern suggests that storey assignment in BIM authoring tools is fundamentally unreliable, and any consistency-checking rule used in production must be class-aware.

**MEP services data fails in MEP-specific ways that a generic audit cannot detect.** Q1 reports zero pset-less elements in the HVAC model — by a naïve audit, the HVAC export looks *more complete* than the Duplex. Q9–Q11 reverse that picture entirely: 100% of flow terminals lack flow rates, 100% of flow elements lack distribution-system assignments, and segments lack diameters. The model passes the architectural completeness tests but fails every Services-specific commissioning requirement. **This is the central technical argument for adopting domain-specific data quality tooling**: generic IDS templates and quality dashboards built around `Pset_WallCommon` or `Pset_DoorCommon` will pass an MEP model that no Services engineer would accept.

The validity result on Q8 (zero failures) is also informative. The controlled vocabularies tested (`FireRating`, `IsExternal`) are not present in the HVAC model, so the rule does not engage. For a complete MEP validation regime the equivalent controlled vocabularies — `FlowDirection` ∈ {`SOURCE`, `SINK`, `SOURCEANDSINK`}, system classification codes, refrigerant types — would need to be added. These are out of scope for this submission but are an obvious next-development step.

---

## 5. Summary of findings

### 5.1 Combined-model summary

| #   | Question                                  | Dimension                 | Duplex    | HVAC      |
| --- | ----------------------------------------- | ------------------------- | --------- | --------- |
| Q1  | Elements with no property sets            | Completeness              | 41        | 0         |
| Q2  | Doors missing FireRating                  | Completeness (compliance) | 0         | 0         |
| Q3  | Elements not in any storey                | Consistency (spatial)     | 122       | 2,114     |
| Q4  | Spaces missing name/number                | Completeness (identity)   | 0         | 0         |
| Q5  | Properties with empty values              | Completeness              | 452       | 10,729    |
| Q6  | Incompleteness by category                | Completeness (agg.)       | 15 ranked | 6 ranked  |
| Q7  | Duplicate identifiers/names               | Uniqueness                | 0 \| 0    | 0 \| 0    |
| Q8  | Values outside permitted set              | Validity                  | 62        | 0         |
| Q9  | Flow terminals missing flow rate          | Completeness (MEP)        | n/a       | 440       |
| Q10 | Flow elements not in a DistributionSystem | Consistency (MEP)         | n/a       | 3,704     |
| Q11 | Flow segments missing diameter            | Completeness (MEP)        | n/a       | 2 classes |

### 5.2 What both models do well

- **Identity dimensions** are excellent in both: every space named, no duplicate GUIDs, no name collisions
- **Uniqueness** is robust: no duplicate global identifiers in either model
- **Property set coverage** is broad in both — the HVAC model averages ~9 Psets per element and the Duplex averages ~9 Psets per element

### 5.3 Where the models diverge

- **Q1 inverts**: the HVAC model is *better* on raw completeness (0 pset-less elements vs. the Duplex's 41). A generic completeness audit would rank the HVAC model as the higher-quality dataset
- **Q3 is worse for HVAC** in both absolute (2,114 vs. 122) and proportional (57% vs. 46%) terms — MEP elements are more frequently unmoored from the spatial hierarchy
- **Q5 is roughly twice as bad** in proportional terms for the HVAC model (7.2% empty vs. 3.4%) — services exports carry more placeholder Psets

### 5.4 Implications for Services BIM

The MEP-specific Q9–Q11 expose failures that the standard architectural audit cannot see:

- **Q9**: every air terminal lacks a populated flow rate — invisible to any check based on `Pset_WallCommon`, `Pset_DoorCommon` or other architectural property sets
- **Q10**: zero `IfcDistributionSystem` entities — invisible to any check that does not specifically look for distribution systems
- **Q11**: some flow elements lack dimensional properties — invisible to any check that does not search the MEP-specific dimensional property names

Generic completeness scoring would rate the HVAC model as 100% compliant on Pset coverage. Services BIM practice requires the discipline-aware extensions developed in §4.1 to detect the failures that matter for commissioning, FM handover and design coordination.

This is the practical justification for treating Services BIM data quality as its own discipline rather than a sub-case of architectural data quality.

---

## 6. Repository layout

```
m7u4-ifc-graph/
├── README.md                           ← this document
├── LICENSE                             ← MIT
├── env.example                         ← template (real .env is gitignored)
├── ifc/
│   ├── Duplex_A_20110907.ifc           ← architectural source (CC-BY-4.0, buildingSMART)
│   └── NBU_MedicalClinic_Eng-HVAC.ifc  ← HVAC source (TIB DURAARK, downloaded externally)
├── notebooks/
│   ├── loader.py                       ← shared batched-MERGE loader with MEP extension
│   ├── 01_extract_and_load.ipynb       ← Duplex ETL
│   ├── 02_data_quality_queries.ipynb   ← eight queries vs. Duplex
│   ├── 02b_data_quality_queries_hvac.ipynb  ← eleven queries vs. HVAC
│   └── 03_extract_and_load_hvac.ipynb  ← HVAC ETL (uses loader.py)
├── queries/                            ← Cypher files (Duplex set)
│   └── hvac/                           ← Cypher files (HVAC set, includes Q9–Q11)
├── results/                            ← CSV exports (Duplex set)
│   └── hvac/                           ← CSV exports (HVAC set)
├── screenshots/
│   ├── 00_graph_overview.png           ← Duplex schema panel
│   ├── 01_spatial_hierarchy.png        ← Duplex spatial chain
│   ├── 02_door_with_properties.png     ← Duplex door + Psets + properties
│   ├── 03_hvac_database_overview.png   ← HVAC schema panel
│   ├── 04_hvac_air_terminal.png        ← HVAC air terminal + Psets + ports
│   ├── 05_hvac_system_topology.png     ← HVAC connected duct chain (port topology)
│   └── 06_hvac_air_terminal_detail.png ← HVAC flow terminals with Node Details
└── docs/
    └── graph_schema.svg                ← graph model diagram (embedded in §2)
```

## 7. How to reproduce

```bash
git clone https://github.com/markshanehaines-ZIG/m7u4-ifc-graph-duplex.git
cd m7u4-ifc-graph-duplex
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash; use venv/bin/activate on macOS/Linux
pip install ifcopenshell neo4j pandas python-dotenv jupyter ipykernel
cp env.example .env            # then edit with your Neo4j credentials
```

The Duplex IFC is included in the repo. The HVAC IFC is not — it is 27 MB and part of a 320 MB academic dataset, redistributable but too large to commit. Download the HVAC source from:

```
https://tib.eu/data/duraark/BuildingData/01_IFC/NBU_MedicalClinic_ifc.zip
```

Extract only `NBU_MedicalClinic_Eng-HVAC.ifc` into `ifc/`.

Then in Neo4j Desktop create a second database called `hvac` alongside the default `neo4j` database (one click — Create database).

```bash
jupyter notebook
```

Run the notebooks in this order:

1. `01_extract_and_load.ipynb` — populates the Duplex graph in the `neo4j` database
2. `02_data_quality_queries.ipynb` — runs the eight queries vs. Duplex, writes to `results/`
3. `03_extract_and_load_hvac.ipynb` — populates the HVAC graph in the `hvac` database
4. `02b_data_quality_queries_hvac.ipynb` — runs the eleven queries vs. HVAC, writes to `results/hvac/`

---

## 8. Standards referenced

- ISO 16739-1:2024 — Industry Foundation Classes
- ISO 19650-1/2 — Information management using BIM
- buildingSMART Sample Test Files (CC-BY-4.0)
- DURAARK project (FP7 EU-funded research), hosted at TIB Hannover
- Lecture material: M7U4 Sessions 1–4, Evelio Sánchez Juncal, Zigurat

---

*End of submission.*
