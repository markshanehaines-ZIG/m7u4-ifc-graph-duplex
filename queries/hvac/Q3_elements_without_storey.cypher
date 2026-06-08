MATCH (e:Element)
WHERE NOT EXISTS {
  MATCH (:Storey)-[:CONTAINS]->(e)
}
RETURN e.GlobalId AS GlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS Name,
       e.Tag      AS Tag
ORDER BY e.IfcClass
