"""
loader.py — IFC to Neo4j graph loader with batched MERGE.

v2 (performance fix): adds backing indexes on PropertySet.pset_id,
Property.prop_id, Type.GlobalId, DistributionPort.GlobalId, and
Material.Name so that MERGE/MATCH operations on those properties
don't trigger full label scans on every batch row.

Used by both the architectural Duplex notebook and the HVAC services notebook.

Schema additions over the original Duplex loader:
    :DistributionPort       MEP connection points (IfcDistributionPort)
    [:HAS_PORT]             Element -> DistributionPort
    [:CONNECTED_TO]         DistributionPort -> DistributionPort

The :DistributionPort extension is only populated if the source IFC contains
IfcDistributionPort entities (i.e. MEP/services models). Architectural-only
models get nothing extra and pay no cost.
"""

from collections import defaultdict
from time import time

import ifcopenshell
import ifcopenshell.util.element
from neo4j import GraphDatabase


class IFCGraphLoader:
    """Load an IFC model into a Neo4j database as a property graph."""

    def __init__(self, ifc_path, neo4j_uri, neo4j_user, neo4j_password,
                 database="neo4j", batch_size=500):
        self.ifc_path = ifc_path
        self.database = database
        self.batch_size = batch_size
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        print(f"Opening IFC: {ifc_path}")
        self.ifc = ifcopenshell.open(str(ifc_path))
        print(f"  Schema: {self.ifc.schema}")
        print(f"  Elements: {len(self.ifc.by_type('IfcElement'))}")
        print(f"Target database: {database}")

    def close(self):
        self.driver.close()

    # ------------------------------------------------------------------ #
    # Internal: batched Cypher execution
    # ------------------------------------------------------------------ #

    def _batch_run(self, cypher, items, label="batch"):
        """Run a Cypher query against a list of items in batches.
        Sends batch_size items per round-trip via UNWIND $batch AS row."""
        if not items:
            return 0
        total = 0
        n_batches = (len(items) + self.batch_size - 1) // self.batch_size
        for i in range(0, len(items), self.batch_size):
            chunk = items[i:i + self.batch_size]
            with self.driver.session(database=self.database) as session:
                session.run(cypher, batch=chunk)
            total += len(chunk)
            if n_batches > 5:
                done_batches = (i // self.batch_size) + 1
                if done_batches % max(1, n_batches // 5) == 0 or done_batches == n_batches:
                    print(f"    {label}: {total}/{len(items)}")
        return total

    def _run(self, cypher, **params):
        """Run a single Cypher query (no batching)."""
        with self.driver.session(database=self.database) as session:
            return list(session.run(cypher, **params))

    # ------------------------------------------------------------------ #
    # Load stages
    # ------------------------------------------------------------------ #

    def wipe_and_constrain(self):
        """Clear the database, (re)create constraints, and create the
        backing indexes that make MERGE/MATCH on non-unique node keys
        run in O(1) instead of scanning the whole label."""
        print(f"\n[1/6] Wipe and constrain")
        t0 = time()

        # Wipe
        self._run("MATCH (n) DETACH DELETE n")

        # Uniqueness constraint on Element.GlobalId (also creates an index)
        self._run("DROP CONSTRAINT element_globalid IF EXISTS")
        self._run("""
            CREATE CONSTRAINT element_globalid IF NOT EXISTS
            FOR (n:Element) REQUIRE n.GlobalId IS UNIQUE
        """)

        # PERFORMANCE INDEXES — required for batched MERGE/MATCH at scale.
        # Without these, every MATCH triggers a full label scan, which makes
        # the HAS_PROPERTY stage O(N^2) and the full load take hours.
        for stmt in [
            "CREATE INDEX propertyset_psetid     IF NOT EXISTS FOR (n:PropertySet)     ON (n.pset_id)",
            "CREATE INDEX property_propid        IF NOT EXISTS FOR (n:Property)        ON (n.prop_id)",
            "CREATE INDEX type_globalid          IF NOT EXISTS FOR (n:Type)            ON (n.GlobalId)",
            "CREATE INDEX distport_globalid      IF NOT EXISTS FOR (n:DistributionPort) ON (n.GlobalId)",
            "CREATE INDEX material_name          IF NOT EXISTS FOR (n:Material)        ON (n.Name)",
            "CREATE INDEX project_globalid       IF NOT EXISTS FOR (n:Project)         ON (n.GlobalId)",
            "CREATE INDEX site_globalid          IF NOT EXISTS FOR (n:Site)            ON (n.GlobalId)",
            "CREATE INDEX building_globalid      IF NOT EXISTS FOR (n:Building)        ON (n.GlobalId)",
            "CREATE INDEX storey_globalid        IF NOT EXISTS FOR (n:Storey)          ON (n.GlobalId)",
            "CREATE INDEX space_globalid         IF NOT EXISTS FOR (n:Space)           ON (n.GlobalId)",
        ]:
            self._run(stmt)

        print(f"  done ({time()-t0:.1f}s)")

    def load_spatial_structure(self):
        """Project, Site, Building, Storey, Space with CONTAINS edges."""
        print("\n[2/6] Spatial structure")
        t0 = time()
        spatial_classes = [
            ("IfcProject", "Project"),
            ("IfcSite", "Site"),
            ("IfcBuilding", "Building"),
            ("IfcBuildingStorey", "Storey"),
            ("IfcSpace", "Space"),
        ]
        counts = {}
        for ifc_class, label in spatial_classes:
            items = []
            for e in self.ifc.by_type(ifc_class):
                items.append({
                    "global_id": e.GlobalId,
                    "ifc_class": ifc_class,
                    "name": getattr(e, "Name", None),
                    "long_name": getattr(e, "LongName", None),
                    "description": getattr(e, "Description", None),
                })
            cypher = f"""
                UNWIND $batch AS row
                MERGE (n:{label} {{GlobalId: row.global_id}})
                SET n.IfcClass = row.ifc_class,
                    n.Name = row.name,
                    n.LongName = row.long_name,
                    n.Description = row.description
            """
            self._batch_run(cypher, items, label=f"{label}")
            counts[label] = len(items)

        agg_rels = []
        spatial_gids = set()
        for label_kv in spatial_classes:
            for e in self.ifc.by_type(label_kv[0]):
                spatial_gids.add(e.GlobalId)
        for rel in self.ifc.by_type("IfcRelAggregates"):
            parent_gid = rel.RelatingObject.GlobalId
            for child in rel.RelatedObjects:
                if child.GlobalId in spatial_gids:
                    agg_rels.append({
                        "parent_gid": parent_gid,
                        "child_gid": child.GlobalId,
                    })
        self._batch_run("""
            UNWIND $batch AS row
            MATCH (parent {GlobalId: row.parent_gid})
            MATCH (child {GlobalId: row.child_gid})
            MERGE (parent)-[:CONTAINS]->(child)
        """, agg_rels, label="agg_rels")

        print(f"  spatial nodes: {counts}")
        print(f"  done ({time()-t0:.1f}s)")
        return counts

    def load_elements(self):
        """All IfcElement subtypes with dual labels and spatial CONTAINS edges."""
        print("\n[3/6] Elements")
        t0 = time()
        elements_by_class = defaultdict(list)
        for e in self.ifc.by_type("IfcElement"):
            elements_by_class[e.is_a()].append({
                "global_id": e.GlobalId,
                "ifc_class": e.is_a(),
                "name": getattr(e, "Name", None),
                "object_type": getattr(e, "ObjectType", None),
                "tag": getattr(e, "Tag", None),
                "description": getattr(e, "Description", None),
            })

        total = 0
        for ifc_class, items in elements_by_class.items():
            cypher = f"""
                UNWIND $batch AS row
                MERGE (e:Element:{ifc_class} {{GlobalId: row.global_id}})
                SET e.IfcClass = row.ifc_class,
                    e.Name = row.name,
                    e.ObjectType = row.object_type,
                    e.Tag = row.tag,
                    e.Description = row.description
            """
            self._batch_run(cypher, items, label=ifc_class)
            total += len(items)

        spatial_rels = []
        for rel in self.ifc.by_type("IfcRelContainedInSpatialStructure"):
            container_gid = rel.RelatingStructure.GlobalId
            for e in rel.RelatedElements:
                spatial_rels.append({
                    "container_gid": container_gid,
                    "element_gid": e.GlobalId,
                })
        self._batch_run("""
            UNWIND $batch AS row
            MATCH (container {GlobalId: row.container_gid})
            MATCH (element:Element {GlobalId: row.element_gid})
            MERGE (container)-[:CONTAINS]->(element)
        """, spatial_rels, label="spatial_containment")

        print(f"  loaded {total} elements across {len(elements_by_class)} classes")
        print(f"  done ({time()-t0:.1f}s)")
        return total

    def load_property_sets(self):
        """PropertySet instances and individual Property leaves."""
        print("\n[4/6] Property sets and properties")
        t0 = time()

        pset_batch, pset_rel_batch = [], []
        prop_batch, prop_rel_batch = [], []

        for obj in self.ifc.by_type("IfcObject"):
            psets = ifcopenshell.util.element.get_psets(obj)
            for pset_name, properties in psets.items():
                pset_gid = f"{obj.GlobalId}__{pset_name}"
                pset_batch.append({"pset_id": pset_gid, "name": pset_name})
                pset_rel_batch.append({
                    "element_gid": obj.GlobalId,
                    "pset_id": pset_gid,
                })
                for prop_name, prop_value in properties.items():
                    if prop_name == "id":
                        continue
                    prop_gid = f"{pset_gid}__{prop_name}"
                    value_str = "" if prop_value is None else str(prop_value)
                    is_empty = prop_value is None or value_str.strip() == ""
                    prop_batch.append({
                        "prop_id": prop_gid,
                        "name": prop_name,
                        "value": value_str,
                        "data_type": type(prop_value).__name__,
                        "is_empty": is_empty,
                    })
                    prop_rel_batch.append({
                        "pset_id": pset_gid,
                        "prop_id": prop_gid,
                    })

        self._batch_run("""
            UNWIND $batch AS row
            MERGE (ps:PropertySet {pset_id: row.pset_id})
            SET ps.Name = row.name
        """, pset_batch, label="psets")

        self._batch_run("""
            UNWIND $batch AS row
            MATCH (e {GlobalId: row.element_gid})
            MATCH (ps:PropertySet {pset_id: row.pset_id})
            MERGE (e)-[:HAS_PSET]->(ps)
        """, pset_rel_batch, label="has_pset")

        self._batch_run("""
            UNWIND $batch AS row
            MERGE (p:Property {prop_id: row.prop_id})
            SET p.Name = row.name,
                p.Value = row.value,
                p.DataType = row.data_type,
                p.IsEmpty = row.is_empty
        """, prop_batch, label="properties")

        self._batch_run("""
            UNWIND $batch AS row
            MATCH (ps:PropertySet {pset_id: row.pset_id})
            MATCH (p:Property {prop_id: row.prop_id})
            MERGE (ps)-[:HAS_PROPERTY]->(p)
        """, prop_rel_batch, label="has_property")

        print(f"  loaded {len(pset_batch)} property sets, {len(prop_batch)} properties")
        print(f"  done ({time()-t0:.1f}s)")
        return len(pset_batch), len(prop_batch)

    def load_types_and_materials(self):
        """IfcTypeObject and IfcMaterial nodes with their element edges."""
        print("\n[5/6] Types and materials")
        t0 = time()

        type_batch = []
        type_rel_batch = []
        seen_types = set()
        for rel in self.ifc.by_type("IfcRelDefinesByType"):
            type_obj = rel.RelatingType
            if type_obj.GlobalId not in seen_types:
                type_batch.append({
                    "global_id": type_obj.GlobalId,
                    "ifc_class": type_obj.is_a(),
                    "name": getattr(type_obj, "Name", None),
                })
                seen_types.add(type_obj.GlobalId)
            for related in rel.RelatedObjects:
                type_rel_batch.append({
                    "element_gid": related.GlobalId,
                    "type_gid": type_obj.GlobalId,
                })

        self._batch_run("""
            UNWIND $batch AS row
            MERGE (t:Type {GlobalId: row.global_id})
            SET t.IfcClass = row.ifc_class,
                t.Name = row.name
        """, type_batch, label="types")

        self._batch_run("""
            UNWIND $batch AS row
            MATCH (e:Element {GlobalId: row.element_gid})
            MATCH (t:Type {GlobalId: row.type_gid})
            MERGE (e)-[:DEFINED_BY]->(t)
        """, type_rel_batch, label="defined_by")

        mat_batch = []
        mat_rel_batch = []
        seen_mats = set()
        for rel in self.ifc.by_type("IfcRelAssociatesMaterial"):
            mat = rel.RelatingMaterial
            if mat.is_a("IfcMaterial"):
                mat_name = mat.Name
            elif hasattr(mat, "Name") and mat.Name:
                mat_name = mat.Name
            else:
                mat_name = mat.is_a()
            if mat_name not in seen_mats:
                mat_batch.append({"name": mat_name})
                seen_mats.add(mat_name)
            for related in rel.RelatedObjects:
                if related.is_a("IfcElement"):
                    mat_rel_batch.append({
                        "element_gid": related.GlobalId,
                        "name": mat_name,
                    })

        self._batch_run("""
            UNWIND $batch AS row
            MERGE (m:Material {Name: row.name})
        """, mat_batch, label="materials")

        self._batch_run("""
            UNWIND $batch AS row
            MATCH (e:Element {GlobalId: row.element_gid})
            MATCH (m:Material {Name: row.name})
            MERGE (e)-[:MADE_OF]->(m)
        """, mat_rel_batch, label="made_of")

        print(f"  loaded {len(type_batch)} types, {len(mat_batch)} materials")
        print(f"  done ({time()-t0:.1f}s)")

    def load_distribution_ports(self):
        """MEP extension: IfcDistributionPort nodes and connection edges."""
        print("\n[6/6] Distribution ports (MEP)")
        t0 = time()
        try:
            ports = self.ifc.by_type("IfcDistributionPort")
        except RuntimeError:
            print("  (IfcDistributionPort not in this schema)")
            return 0

        if not ports:
            print("  (no ports in this model — skipping)")
            return 0

        port_batch = []
        for p in ports:
            port_batch.append({
                "global_id": p.GlobalId,
                "name": getattr(p, "Name", None),
                "flow_direction": str(getattr(p, "FlowDirection", "") or ""),
            })
        self._batch_run("""
            UNWIND $batch AS row
            MERGE (p:DistributionPort {GlobalId: row.global_id})
            SET p.Name = row.name,
                p.FlowDirection = row.flow_direction
        """, port_batch, label="ports")

        elem_port_batch = []
        for rel in self.ifc.by_type("IfcRelConnectsPortToElement"):
            elem_port_batch.append({
                "port_gid": rel.RelatingPort.GlobalId,
                "element_gid": rel.RelatedElement.GlobalId,
            })
        self._batch_run("""
            UNWIND $batch AS row
            MATCH (e:Element {GlobalId: row.element_gid})
            MATCH (p:DistributionPort {GlobalId: row.port_gid})
            MERGE (e)-[:HAS_PORT]->(p)
        """, elem_port_batch, label="has_port")

        port_port_batch = []
        for rel in self.ifc.by_type("IfcRelConnectsPorts"):
            port_port_batch.append({
                "from_gid": rel.RelatingPort.GlobalId,
                "to_gid": rel.RelatedPort.GlobalId,
            })
        self._batch_run("""
            UNWIND $batch AS row
            MATCH (p1:DistributionPort {GlobalId: row.from_gid})
            MATCH (p2:DistributionPort {GlobalId: row.to_gid})
            MERGE (p1)-[:CONNECTED_TO]->(p2)
        """, port_port_batch, label="connected_to")

        print(f"  loaded {len(port_batch)} ports, "
              f"{len(elem_port_batch)} element-port links, "
              f"{len(port_port_batch)} port-port connections")
        print(f"  done ({time()-t0:.1f}s)")
        return len(port_batch)

    def verify(self):
        """Print node and relationship counts."""
        print("\n=== Graph load summary ===")
        for r in self._run("""
            MATCH (n) UNWIND labels(n) AS lbl
            RETURN lbl, count(*) AS c
            ORDER BY c DESC
        """):
            print(f"  {r['lbl']:30s} {r['c']}")
        print()
        for r in self._run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel, count(*) AS c
            ORDER BY c DESC
        """):
            print(f"  {r['rel']:30s} {r['c']}")

    def run_all(self):
        """Run every stage in order."""
        t0 = time()
        self.wipe_and_constrain()
        self.load_spatial_structure()
        self.load_elements()
        self.load_property_sets()
        self.load_types_and_materials()
        self.load_distribution_ports()
        self.verify()
        print(f"\nTotal load time: {time()-t0:.1f}s")
