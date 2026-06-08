MATCH (e:Element)-[:HAS_PSET]->(ps:PropertySet)-[:HAS_PROPERTY]->(p:Property)
WHERE p.IsEmpty = true
RETURN e.GlobalId AS ElementGlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS ElementName,
       ps.Name    AS PropertySet,
       p.Name     AS PropertyName,
       p.DataType AS DataType
ORDER BY e.IfcClass, ps.Name, p.Name
