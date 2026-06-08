MATCH (e:Element)
WHERE NOT (e)-[:HAS_PSET]->()
RETURN e.GlobalId AS GlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS Name,
       e.Tag      AS Tag
ORDER BY e.IfcClass, e.Name
