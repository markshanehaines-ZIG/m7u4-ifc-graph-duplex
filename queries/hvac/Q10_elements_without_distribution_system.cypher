MATCH (e:Element)
WHERE e.IfcClass IN ['IfcFlowSegment','IfcFlowFitting','IfcFlowTerminal',
                     'IfcFlowController','IfcFlowMovingDevice',
                     'IfcEnergyConversionDevice']
RETURN e.IfcClass AS IfcClass,
       count(*)   AS UnassignedCount
ORDER BY UnassignedCount DESC
