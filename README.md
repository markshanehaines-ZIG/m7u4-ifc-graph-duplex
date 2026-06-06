# BIMGUARD AI — NotebookLM Reference Library

## What this is

This directory contains everything needed to understand, recreate, and query the BIMGUARD AI NotebookLM — a structured knowledge base built to support the BIMGUARD AI Final Master Project (FMP) at Zigurat Global Institute of Technology, Masters in BIM Management.

The NotebookLM acts as the technical brain of the BIMGUARD AI system. It centralises the engineering standards, dimensional tables, material data, IFC schema definitions, and ISO 19650 governance frameworks that the tool's five compliance phases draw upon. Rather than embedding static lookup tables in the application code, BIMGUARD uses the NotebookLM as a queryable reference layer — a Retrieval-Augmented Generation (RAG) approach where every calculation can be traced back to a named standard and a specific source document.

## Live notebook access

The shared NotebookLM can be accessed at the link below. Any Google account holder can open it, browse the loaded sources, and submit queries.

> **[Insert NotebookLM share link here]**

To generate the share link: open the notebook in NotebookLM → click the share icon (top right) → select "Anyone with the link can view" → copy and paste the URL above.

## What the notebook contains

The notebook is loaded with 36 source URLs covering six subject domains:

| Domain | Coverage |
|--------|----------|
| Centre-to-centre spacing | C-to-C formula, pipe spacing charts, flange clearance tables |
| Pipe dimensions | NPS/DN conversion, OD by schedule, ASME B36.10M, API 5L |
| Flange dimensions | ASME B16.5 (Classes 150–2500), EN 1092-1 (PN6–PN40) |
| Thermal expansion | Coefficients by material, expansion loop design, kinematic clash |
| Galvanic corrosion | Galvanic series, anodic index, voltage thresholds, material compatibility |
| BIM standards | IFC 4.3 schema, ISO 19650 Parts 1–3, IMI Framework guidance |

The full list of source URLs with descriptions is in `sources.md`.

## How to recreate this notebook

See `setup_guide.md` for step-by-step instructions to build an identical notebook from scratch using the sources in this directory.

## How to query it

See `master_prompt.md` for the system-level master prompt that configures the notebook's behaviour, plus a library of pre-built query templates for each BIMGUARD compliance phase.

## Repository context

This NotebookLM directory is one component of the wider BIMGUARD AI repository, which also contains:

- `/engines` — Python source for GC-001 (galvanic) and CC-001 (crevice) corrosion engines
- `/app` — Streamlit web application source
- `/rulesets` — JSON rulesets for GC-001 and CC-001
- `/docs` — Thesis chapters and presentation decks
- `/notebooklm` — This directory

## Academic context

**Programme:** Masters in BIM Management  
**Institution:** Zigurat Global Institute of Technology  
**Project:** BIMGUARD AI — Automated BIM Corrosion Compliance Checker  
**Group:** Group 5  
**Methodology:** OpenBIM (IFC ISO 16739-1, BCF 2.1, ISO 19650)
