// Q2 — Completeness (compliance-critical)
// Doors should carry Pset_DoorCommon.FireRating for compartmentation checks.
// We split the result into two states:
//   "Missing" — no FireRating property exists at all
//   "Empty"   — the property exists but its value is blank
// Both states fail a fire-safety compliance check.

MATCH (d:Element:IfcDoor)
OPTIONAL MATCH (d)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property {Name: 'FireRating'})
WITH d, p
WHERE p IS NULL OR p.IsEmpty = true
RETURN d.GlobalId AS GlobalId,
       d.Name     AS DoorName,
       d.Tag      AS Tag,
       CASE WHEN p IS NULL THEN 'Missing' ELSE 'Empty' END AS FireRatingStatus,
       p.Value    AS RawValue
ORDER BY FireRatingStatus, d.Name
