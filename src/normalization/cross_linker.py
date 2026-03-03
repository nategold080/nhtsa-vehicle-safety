"""Cross-link complaints, recalls, and investigations."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

from src.normalization.vehicles import normalize_make, normalize_model


def cross_link_all(conn: sqlite3.Connection) -> dict:
    """Run all cross-linking strategies and return counts."""
    results = {}
    results["complaint_to_recall"] = link_complaints_to_recalls(conn)
    results["complaint_to_investigation"] = link_complaints_to_investigations(conn)
    results["recall_to_investigation"] = link_recalls_to_investigations(conn)
    conn.commit()
    return results


def link_complaints_to_recalls(conn: sqlite3.Connection) -> int:
    """Link complaints to recalls by make/model/year and component overlap."""
    # Get all recalls indexed by normalized make/model/year
    recalls = conn.execute("""
        SELECT campaign_number, make, model, model_year, component
        FROM recalls
    """).fetchall()

    recall_index = defaultdict(list)
    for r in recalls:
        key = f"{normalize_make(r['make'])}|{normalize_model(r['model'])}|{r['model_year']}"
        recall_index[key].append({
            "campaign_number": r["campaign_number"],
            "component": r["component"].upper(),
        })

    # Iterate through complaints and find matching recalls
    complaints = conn.execute("""
        SELECT odi_number, make, model, model_year, components
        FROM complaints
    """).fetchall()

    linked = 0
    batch = []
    for c in complaints:
        key = f"{normalize_make(c['make'])}|{normalize_model(c['model'])}|{c['model_year']}"
        matching_recalls = recall_index.get(key, [])

        for recall in matching_recalls:
            # Check component overlap — use prefix matching since NHTSA uses
            # hierarchical components like "WHEELS:LUGS/NUTS/BOLTS/STUDS"
            complaint_comps = [s.strip() for s in c["components"].upper().split(",") if s.strip()] if c["components"] else []
            recall_comps = [s.strip() for s in recall["component"].upper().replace(":", ",").split(",") if s.strip()] if recall["component"] else []

            has_overlap = False
            if not complaint_comps or not recall_comps:
                has_overlap = True  # If either side is empty, match on make/model/year alone
            else:
                for cc in complaint_comps:
                    for rc in recall_comps:
                        if cc == rc or cc.startswith(rc) or rc.startswith(cc):
                            has_overlap = True
                            break

            if has_overlap:
                confidence = 0.9 if complaint_comps and recall_comps and has_overlap else 0.6
                batch.append({
                    "source_type": "complaint",
                    "source_id": str(c["odi_number"]),
                    "target_type": "recall",
                    "target_id": recall["campaign_number"],
                    "link_method": "make_model_year_component",
                    "confidence": confidence,
                })
                linked += 1

    # Batch insert
    for rec in batch:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO cross_links
                (source_type, source_id, target_type, target_id, link_method, confidence)
                VALUES (:source_type, :source_id, :target_type, :target_id, :link_method, :confidence)
            """, rec)
        except sqlite3.IntegrityError:
            pass

    return linked


def link_complaints_to_investigations(conn: sqlite3.Connection) -> int:
    """Link complaints to investigations by make/model/year range."""
    investigations = conn.execute("""
        SELECT investigation_number, make, model, model_year_start, model_year_end, subject
        FROM investigations
        WHERE make != '' AND model_year_start > 0
    """).fetchall()

    inv_by_make = defaultdict(list)
    for inv in investigations:
        make_norm = normalize_make(inv["make"])
        inv_by_make[make_norm].append({
            "investigation_number": inv["investigation_number"],
            "model": normalize_model(inv["model"]) if inv["model"] else "",
            "year_start": inv["model_year_start"],
            "year_end": inv["model_year_end"] or inv["model_year_start"],
            "subject": inv["subject"],
        })

    complaints = conn.execute("""
        SELECT odi_number, make, model, model_year
        FROM complaints
    """).fetchall()

    linked = 0
    batch = []
    for c in complaints:
        make_norm = normalize_make(c["make"])
        model_norm = normalize_model(c["model"])

        for inv in inv_by_make.get(make_norm, []):
            # Year must be in range
            if not (inv["year_start"] <= c["model_year"] <= inv["year_end"]):
                continue

            # Model match (if investigation specifies one)
            if inv["model"] and inv["model"] != model_norm:
                continue

            batch.append({
                "source_type": "complaint",
                "source_id": str(c["odi_number"]),
                "target_type": "investigation",
                "target_id": inv["investigation_number"],
                "link_method": "make_model_year_range",
                "confidence": 0.7 if inv["model"] else 0.5,
            })
            linked += 1

    for rec in batch:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO cross_links
                (source_type, source_id, target_type, target_id, link_method, confidence)
                VALUES (:source_type, :source_id, :target_type, :target_id, :link_method, :confidence)
            """, rec)
        except sqlite3.IntegrityError:
            pass

    return linked


def link_recalls_to_investigations(conn: sqlite3.Connection) -> int:
    """Link recalls to investigations by make/model/year and component."""
    recalls = conn.execute("""
        SELECT campaign_number, make, model, model_year, component
        FROM recalls
    """).fetchall()

    investigations = conn.execute("""
        SELECT investigation_number, make, model, model_year_start, model_year_end, subject, components
        FROM investigations
        WHERE make != ''
    """).fetchall()

    linked = 0
    batch = []
    for r in recalls:
        r_make = normalize_make(r["make"])
        r_model = normalize_model(r["model"])

        for inv in investigations:
            i_make = normalize_make(inv["make"])
            if r_make != i_make:
                continue

            i_model = normalize_model(inv["model"]) if inv["model"] else ""
            if i_model and i_model != r_model:
                continue

            year_start = inv["model_year_start"] or 0
            year_end = inv["model_year_end"] or year_start
            if year_start and not (year_start <= r["model_year"] <= year_end):
                continue

            batch.append({
                "source_type": "recall",
                "source_id": r["campaign_number"],
                "target_type": "investigation",
                "target_id": inv["investigation_number"],
                "link_method": "make_model_year",
                "confidence": 0.8,
            })
            linked += 1

    for rec in batch:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO cross_links
                (source_type, source_id, target_type, target_id, link_method, confidence)
                VALUES (:source_type, :source_id, :target_type, :target_id, :link_method, :confidence)
            """, rec)
        except sqlite3.IntegrityError:
            pass

    return linked
