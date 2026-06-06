// Q5 — Completeness (the "illusion of structured data")
// Lecture 2: "Exporting a Pset does not mean exporting useful information.
// Empty placeholders create the illusion of structured data."
// We pre-computed IsEmpty=true at load time for any property whose value is
// null or whitespace-only, so this query is now a direct lookup.

MATCH (e:Element)-[:HAS_PSET]->(ps:PropertySet)-[:HAS_PROPERTY]->(p:Property)
WHERE p.IsEmpty = true
RETURN e.GlobalId AS ElementGlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS ElementName,
       ps.Name    AS PropertySet,
       p.Name     AS PropertyName,
       p.DataType AS DataType
ORDER BY e.IfcClass, ps.Name, p.Name
