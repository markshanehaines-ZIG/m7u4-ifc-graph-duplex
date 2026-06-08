MATCH (s:Space)
WHERE s.Name IS NULL     OR trim(s.Name) = ''
   OR s.LongName IS NULL OR trim(s.LongName) = ''
RETURN s.GlobalId                              AS GlobalId,
       coalesce(s.Name, '<MISSING>')           AS RoomNumber,
       coalesce(s.LongName, '<MISSING>')       AS RoomName,
       s.Description                           AS Description
ORDER BY s.GlobalId
