MATCH (e:Element)
OPTIONAL MATCH (e)-[:HAS_PSET]->(:PropertySet)-[:HAS_PROPERTY]->(p:Property)
WITH e.IfcClass AS Category, e, p
WITH Category,
     count(DISTINCT e) AS TotalElements,
     sum(CASE WHEN p IS NULL THEN 1 ELSE 0 END) AS ElementsNoProperties,
     count(p) AS TotalProperties,
     sum(CASE WHEN p.IsEmpty = true THEN 1 ELSE 0 END) AS EmptyProperties
RETURN Category, TotalElements, TotalProperties, EmptyProperties,
       CASE WHEN TotalProperties = 0 THEN 0.0
            ELSE round(toFloat(EmptyProperties) / TotalProperties, 3)
       END AS EmptyRatio
ORDER BY EmptyProperties DESC, EmptyRatio DESC
