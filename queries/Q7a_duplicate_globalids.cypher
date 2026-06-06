// Q7a — Uniqueness (GlobalId)
// IFC GlobalIds are required to be globally unique. A duplicate here would
// indicate a serious modelling or export defect.
MATCH (e:Element)
WITH e.GlobalId AS GlobalId, count(*) AS Occurrences, collect(e.IfcClass) AS Classes
WHERE Occurrences > 1
RETURN GlobalId, Occurrences, Classes
