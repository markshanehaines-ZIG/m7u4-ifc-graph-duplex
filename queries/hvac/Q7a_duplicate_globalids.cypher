MATCH (e:Element)
WITH e.GlobalId AS GlobalId, count(*) AS Occurrences, collect(e.IfcClass) AS Classes
WHERE Occurrences > 1
RETURN GlobalId, Occurrences, Classes
