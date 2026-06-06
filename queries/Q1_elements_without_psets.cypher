// Q1 — Completeness
// Find every :Element node that has no outgoing HAS_PSET relationship.
// Such elements carry no semantic metadata beyond their IFC class and name,
// breaking downstream uses (cost, scheduling, FM handover).

MATCH (e:Element)
WHERE NOT (e)-[:HAS_PSET]->()
RETURN e.GlobalId AS GlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS Name,
       e.Tag      AS Tag
ORDER BY e.IfcClass, e.Name
