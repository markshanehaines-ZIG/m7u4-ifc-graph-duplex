// Q8 — Validity (controlled vocabulary)
// Two checks against known controlled vocabularies:
//   FireRating  — numeric minutes (30/60/90/120/180/240) or "FDxx" codes
//   IsExternal  — boolean (must be true/false, case-insensitive)
// Anything outside these sets is a validity failure: the value exists but is
// not interpretable by a downstream compliance engine.

MATCH (e:Element)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property)
WHERE p.IsEmpty = false
  AND (
    (p.Name = 'FireRating'
       AND NOT p.Value IN ['30','60','90','120','180','240',
                           'FD30','FD60','FD90','FD120','FD180','FD240'])
    OR
    (p.Name = 'IsExternal'
       AND NOT toLower(p.Value) IN ['true','false'])
  )
RETURN e.GlobalId AS ElementGlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS ElementName,
       p.Name     AS PropertyName,
       p.Value    AS RawValue,
       p.DataType AS DataType
ORDER BY p.Name, p.Value
