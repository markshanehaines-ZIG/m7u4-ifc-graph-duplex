// Q7b — Uniqueness (Name within IFC class)
// In IFC it is common for many instances to share a Name (e.g. "Basic Wall:200mm")
// because the Name carries the type/family rather than an instance identifier.
// High duplication counts are not strictly errors but signal weak individual
// identification — a problem for asset tagging and FM lookup.
MATCH (e:Element)
WHERE e.Name IS NOT NULL AND trim(e.Name) <> ''
WITH e.IfcClass AS IfcClass, e.Name AS Name,
     count(*) AS Occurrences, collect(e.GlobalId)[..5] AS SampleGlobalIds
WHERE Occurrences > 1
RETURN IfcClass, Name, Occurrences, SampleGlobalIds
ORDER BY Occurrences DESC, IfcClass, Name
