MATCH (e:Element)
WHERE e.IfcClass IN ['IfcFlowSegment','IfcFlowFitting']
  AND NOT EXISTS {
    MATCH (e)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property)
    WHERE p.IsEmpty = false
      AND p.Name IN ['NominalDiameter','OuterDiameter','InnerDiameter',
                     'NominalWidth','NominalHeight','Width','Height']
  }
RETURN e.IfcClass AS IfcClass,
       count(*)   AS SegmentsMissingDiameter
ORDER BY SegmentsMissingDiameter DESC
