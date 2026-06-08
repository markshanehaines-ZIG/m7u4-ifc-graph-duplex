MATCH (e:Element)
WHERE e.Name IS NOT NULL AND trim(e.Name) <> ''
WITH e.IfcClass AS IfcClass, e.Name AS Name,
     count(*) AS Occurrences, collect(e.GlobalId)[..5] AS SampleGlobalIds
WHERE Occurrences > 1
RETURN IfcClass, Name, Occurrences, SampleGlobalIds
ORDER BY Occurrences DESC, IfcClass, Name
