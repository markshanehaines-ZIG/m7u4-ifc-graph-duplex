// Q3 — Consistency (spatial integrity)
// Every physical element should be spatially contained by a Storey
// (via IfcRelContainedInSpatialStructure → CONTAINS in our graph).
// Orphaned elements break automated quantity take-offs, energy simulations,
// and any storey-based dashboard.

MATCH (e:Element)
WHERE NOT EXISTS {
  MATCH (:Storey)-[:CONTAINS]->(e)
}
RETURN e.GlobalId AS GlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS Name,
       e.Tag      AS Tag
ORDER BY e.IfcClass
