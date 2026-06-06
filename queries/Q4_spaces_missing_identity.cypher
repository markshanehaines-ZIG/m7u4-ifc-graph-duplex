// Q4 — Completeness (identity)
// In IFC, IfcSpace.Name typically holds the room number (e.g. "101")
// and IfcSpace.LongName holds the descriptive name (e.g. "Living Room").
// A space missing either cannot be referenced in FM systems or area schedules.

MATCH (s:Space)
WHERE s.Name IS NULL     OR trim(s.Name) = ''
   OR s.LongName IS NULL OR trim(s.LongName) = ''
RETURN s.GlobalId                              AS GlobalId,
       coalesce(s.Name, '<MISSING>')           AS RoomNumber,
       coalesce(s.LongName, '<MISSING>')       AS RoomName,
       s.Description                           AS Description
ORDER BY s.GlobalId
