MATCH (e:Element:IfcFlowTerminal)
WHERE NOT EXISTS {
  MATCH (e)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property)
  WHERE p.IsEmpty = false
    AND (p.Name IN ['NominalAirflowRate','AirflowRate','FlowRate','NominalFlowRate'])
}
RETURN e.GlobalId AS GlobalId,
       e.IfcClass AS IfcClass,
       e.Name     AS Name,
       e.Tag      AS Tag
ORDER BY e.Name
