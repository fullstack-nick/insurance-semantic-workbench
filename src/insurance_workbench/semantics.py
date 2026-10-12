"""Deterministic source interpretation, RDFS materialization and SHACL validation."""

import json
from decimal import Decimal, InvalidOperation

from owlrl import DeductiveClosure, RDFS_Semantics
from pyshacl import validate
from rdflib import RDF, SKOS, XSD, Graph, Literal, Namespace

from .config import ROOT
from .util import digest, json_text

ISW = Namespace("https://example.org/isw/term/")
ENTITY = Namespace("https://example.org/isw/entity/")
CZ = Namespace("https://example.org/isw/cz/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SH = Namespace("http://www.w3.org/ns/shacl#")
SEMANTIC = ROOT / "semantic"


def ontology(release, root=SEMANTIC):
    catalog = json.loads((root / "catalog.json").read_text())
    g = Graph()
    for name, expected in catalog["modules"].items():
        if name == "shapes.ttl":
            continue
        path = root / name
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"Local ontology catalog mismatch: {name}")
        g.parse(path, format="turtle")
    g.parse(root / release / "vocabulary.ttl", format="turtle")
    return g


def shapes(release, root=SEMANTIC):
    g = Graph().parse(root / "shapes.ttl", format="turtle")
    if release == "2.0.0":
        g.parse(root / release / "readiness.ttl", format="turtle")
    return g


def applicable(versions, loss_date):
    if not loss_date:
        return []
    return [
        v
        for v in versions
        if v["valid_from"] <= loss_date and (not v.get("valid_to") or loss_date < v["valid_to"])
    ]


def source_context(records, release, root=SEMANTIC):
    mappings = json.loads((root / release / "mappings.json").read_text(encoding="utf-8"))
    identities = {
        (m["source_system"], m["source_id"]): m["entity_id"]
        for m in json.loads((root / "identity-crosswalks.json").read_text())
        if m["status"] == "approved"
    }
    cases = {}
    for cid, source in records.items():
        if source["kind"] != "claim":
            continue
        p = source["payload"]
        policy_source = records.get(p["policy_id"])
        policy = policy_source["payload"] if policy_source else None
        versions = applicable(policy["versions"], p.get("loss_date")) if policy else []
        observations = p.get("observations", [])
        causes = sorted({o["cause"] for o in observations})
        specific = [c for c in causes if c != "water-damage"]
        mapping = mappings["codes"].get(p["country"] + ":" + p["source_code"])
        classification = (
            specific[0]
            if mapping and mappings["narrowing_enabled"] and len(causes) == 1 and specific
            else mapping["target"]
            if mapping
            else "water-damage"
        )
        missing = []
        if not mapping:
            missing.append(
                "Source code has no approved mapping; retain unresolved broad context for steward review"
            )
        if not p.get("loss_date"):
            missing.append("Loss date is missing; historical policy context cannot be selected")
        if len(versions) != 1:
            missing.append(
                "Policy context is ambiguous: overlapping periods"
                if len(versions) > 1
                else "No unambiguous applicable policy version"
            )
        if policy and policy["country"] != p["country"]:
            missing.append("Claim and policy operating countries disagree")
            versions = []
        if p["country"] == "CZ" and not p.get("mitigation"):
            missing.append("CZ profile requires a mitigation assessment")
        if mappings["narrowing_enabled"] and classification == "water-damage":
            missing.append("Specific cause is not established under release 2 readiness rules")
        if p.get("identity_candidate") and (
            identities.get(("claims-api", p["identity_candidate"])) is None
            or identities.get(("claims-api", p["identity_candidate"]))
            != identities.get(("claims-api", p["reporter"]["id"]))
        ):
            missing.append("Possible identity match is unapproved; entities remain separate")
        status = "conflicted" if len(causes) > 1 else "incomplete" if missing else "sufficient"
        cases[cid] = {
            "id": cid,
            "country": p["country"],
            "summary": p.get("summary", "Claim review"),
            "claim": p,
            "claim_source": source["id"],
            "policy": policy,
            "policy_source": policy_source["id"] if policy_source else None,
            "policy_versions": versions if len(versions) == 1 else [],
            "candidate_versions": versions,
            "classification": classification,
            "source_code": p["source_code"],
            "mapping_known": bool(mapping),
            "status": status,
            "missing": missing,
            "conflicts": observations if len(causes) > 1 else [],
            "findings": [],
            "quarantined": False,
        }
    return cases


def evidence_for(case, records, release, projection, vocabulary=None):
    if case["quarantined"]:
        return []
    items = []
    cid = case["id"]

    def add(group, text, source, kind="fact", locator=None, language="en", **extra):
        if not source:
            return
        group_id = f"{cid}/{group}"
        eid = "ev-" + digest([projection, group_id, source["id"], text])[:24]
        payload = {
            "evidence_id": eid,
            "group_id": group_id,
            "case_scope": cid,
            "country_scope": case["country"],
            "kind": kind,
            "source_system": {
                "claim": "claims-api",
                "policy": "policy-sql",
                "document": "document-repository",
            }[source["kind"]],
            "source_id": source["aggregate_id"],
            "source_version": source["version"],
            "source_snapshot_id": source["id"],
            "content_sha256": source["sha256"],
            "locator": locator or {"type": "json-pointer", "pointer": "/"},
            "text_or_value": text,
            "language": language,
            "valid_from": None,
            "valid_to": None,
            "ingested_at": str(source["created_at"]),
            "mapping_release_id": release,
            "semantic_release_id": release,
            "projection_id": projection,
            "transformation_id": f"transform-{projection}",
            **extra,
        }
        items.append(payload)

    claim = records[cid]
    p = claim["payload"]
    related = [
        source
        for source in records.values()
        if source["kind"] == "claim"
        and source["country"] == case["country"]
        and source["payload"]["loss_id"] == p["loss_id"]
    ]
    add(
        "claim",
        f"Claim {cid}; loss event {p['loss_id']}; loss date {p.get('loss_date') or 'MISSING'}; operation {p['country']}; source code {p['source_code']} "
        + ("means broad water damage. " if case["mapping_known"] else "has no approved mapping. ")
        + f"Recorded amount {p['amount']} {p['currency']}.",
        claim,
    )
    add(
        "roles",
        f"Reporter {p['reporter']['name']} ({p['reporter']['id']}) acts in the reporter role for claim {cid}. Unapproved identity candidates are not merged.",
        claim,
        locator={"type": "json-pointer", "pointer": "/reporter"},
    )
    if len(related) > 1:
        add(
            "shared-loss",
            f"Loss event {p['loss_id']} is referenced by distinct claims "
            + ", ".join(sorted(source["aggregate_id"] for source in related))
            + ". Their claim identities remain separate; no other claim details are included.",
            claim,
            locator={"type": "json-pointer", "pointer": "/loss_id"},
            supporting_sources=[
                {"source_snapshot_id": source["id"], "sha256": source["sha256"], "pointer": "/loss_id"}
                for source in related
            ],
        )
    add(
        "classification",
        f"Semantic release {release} classifies {cid} as {case['classification']}. "
        "The source code alone establishes only water damage; a narrower classification requires one unambiguous source cause. "
        + "Approved labels: "
        + "; ".join(
            sorted(
                f"{label.language}: {label}"
                for label in (vocabulary or ontology(release)).objects(
                    ISW["concept/" + case["classification"]], SKOS.prefLabel
                )
            )
        ),
        claim,
        locator={"type": "json-pointer", "pointer": "/observations", "mapping": f"{release}/mappings.json"},
    )
    for obs in p.get("observations", []):
        add(
            "assertion-" + obs["id"],
            f"{obs['by']} assertion: {obs['text']} Reported cause: {obs['cause']}.",
            claim,
            kind="assertion",
            locator={"type": "json-pointer", "pointer": f"/observations/{p['observations'].index(obs)}"},
            cause=obs["cause"],
        )
    if p.get("mitigation"):
        add(
            "mitigation",
            p["mitigation"]["text"],
            claim,
            locator={"type": "json-pointer", "pointer": "/mitigation"},
        )
    policy = case["policy"]
    if len(case["policy_versions"]) == 1 and policy:
        v = case["policy_versions"][0]
        src = records[policy["id"]]
        document = records.get(v["document_id"])
        add(
            "insured-role",
            f"Party {policy['party']['id']} is insured under policy {policy['id']}. "
            "This contextual role is distinct from the claim reporter role; only approved source-ID crosswalks join identities.",
            src,
            locator={"type": "sql-snapshot", "table": "policies", "row": policy["id"], "field": "party"},
        )
        add(
            "policy",
            f"Policy {policy['id']} version {v['id']} applies from {v['valid_from']} inclusive to {v.get('valid_to') or 'open end'} exclusive. Loss {p.get('loss_date')}. Product {policy['product']}; operating profile {policy['country']}; property location {policy['property_country']}.",
            src,
            locator={"type": "sql-snapshot", "table": "policy_versions", "row": v["id"], "field": "period"},
            valid_from=v["valid_from"],
            valid_to=v.get("valid_to"),
        )
        add(
            "coverage",
            f"Purchased coverages for {v['id']}: {', '.join(v['coverages'])}. Offered but unpurchased: {', '.join(sorted(set(policy['offered_coverages']) - set(v['coverages']))) or 'none'}. Contract document {v['document_id']}. Insured party {policy['party']['id']}.",
            src,
            locator={
                "type": "sql-snapshot",
                "table": "policy_versions",
                "row": v["id"],
                "field": "coverages",
            },
        )
        if document:
            d = document["payload"]
            valid = (
                d["country"] == case["country"]
                and d["valid_from"] <= p["loss_date"]
                and (not d.get("valid_to") or p["loss_date"] < d["valid_to"])
            )
            if valid:
                for clause in d["clauses"]:
                    if clause["coverage"] not in [*v["coverages"], "duties", "mitigation"]:
                        continue
                    add(
                        "clause-" + clause["id"],
                        d["text"][clause["start"] : clause["end"]],
                        document,
                        "clause",
                        locator={
                            "type": "document-span",
                            "document_version": d["id"],
                            "clause": clause["id"],
                            "start": clause["start"],
                            "end": clause["end"],
                            "normalization": "UTF-8 decoded; LF; Unicode character offsets",
                        },
                        language=d["language"],
                        valid_from=d["valid_from"],
                        valid_to=d.get("valid_to"),
                        original_bytes_sha256=digest(d["text"].encode("utf-8")),
                    )
            else:
                case["missing"].append(
                    "Contract document applicability does not match the policy and loss date"
                )
        else:
            case["missing"].append("Applicable contract document is unavailable")
    return items


def _graphs(records, cases, items, release, projection, excluded=frozenset(), root=SEMANTIC):
    base = ontology(release, root)
    graphs = {country: Graph() + base for country in ["AT", "CZ"]}
    owners = {}

    def lit(g, node, prop, value, datatype=None):
        if value is not None:
            g.add((node, prop, Literal(value, datatype=datatype)))

    for country, g in graphs.items():
        g.bind("isw", ISW)
        g.bind("entity", ENTITY)
        g.bind("prov", PROV)
        rel = ENTITY[f"release-{release}"]
        g.add((rel, RDF.type, ISW.SemanticRelease))
        if release == "2.0.0":
            g.add((rel, ISW.predecessor, ENTITY["release-1.0.0"]))
        for code, mapping in json.loads((root / release / "mappings.json").read_text())["codes"].items():
            if not code.startswith(country + ":"):
                continue
            node = ENTITY["mapping-" + code.replace(":", "-")]
            g.add((node, RDF.type, ISW.MappingReview))
            g.add((node, ISW.mappingTarget, ISW["concept/" + mapping["target"]]))
            lit(g, node, ISW.mappingStrength, mapping["strength"])
            lit(g, node, ISW.status, "approved")
            lit(g, node, ISW.owner, mapping["owner"])
        for crosswalk in json.loads((root / "identity-crosswalks.json").read_text()):
            if crosswalk["country"] != country:
                continue
            party = ENTITY[crosswalk["entity_id"]]
            record = ENTITY[crosswalk["source_system"] + "-" + crosswalk["source_id"]]
            g.add((party, RDF.type, ISW.Party))
            g.add((party, ISW.crosswalk, record))
            g.add((record, RDF.type, ISW.SourceRecord))
            lit(g, record, ISW.namespace, crosswalk["source_system"])
            lit(g, record, ISW.sourceId, crosswalk["source_id"])
            lit(g, record, ISW.status, "approved")
        for consumer in json.loads((root / "consumers.json").read_text()):
            node = ENTITY["consumer-" + consumer["id"]]
            g.add((node, RDF.type, ISW.ConsumerDependency))
            for term in consumer["terms"]:
                g.add((node, ISW.dependsOn, ISW[term]))
    for aggregate, src in records.items():
        if aggregate in excluded:
            continue
        p = src["payload"]
        g = graphs[src["country"]]
        node = ENTITY[aggregate]
        snapshot = ENTITY[src["id"]]
        owners[str(node)] = aggregate
        owners[str(snapshot)] = aggregate
        g.add((snapshot, RDF.type, ISW.SourceSnapshot))
        lit(g, snapshot, ISW.sourceId, aggregate)
        lit(g, snapshot, ISW.sha256, src["sha256"])
        lit(g, snapshot, ISW.namespace, "source/" + src["kind"])
        g.add((snapshot, PROV.wasGeneratedBy, ENTITY[f"ingest-{src['id']}"]))
        g.add((node, PROV.wasDerivedFrom, snapshot))
        if src["kind"] == "policy":
            g.add((node, RDF.type, ISW.Policy))
            lit(g, node, ISW.country, p["country"])
            lit(g, node, ISW.propertyCountry, p["property_country"])
            prod = ENTITY[p["product"].replace(" ", "-")]
            g.add((node, ISW.product, prod))
            g.add((prod, RDF.type, ISW.Product))
            for offered in p["offered_coverages"]:
                g.add((prod, ISW.offeredCoverage, ISW[f"concept/{offered}"]))
            for v in p["versions"]:
                vn = ENTITY[v["id"]]
                owners[str(vn)] = aggregate
                g.add((node, ISW.hasVersion, vn))
                g.add((vn, RDF.type, ISW.PolicyVersion))
                lit(g, vn, ISW.validFrom, v["valid_from"], XSD.date)
                lit(g, vn, ISW.validTo, v.get("valid_to"), XSD.date)
                g.add((vn, ISW.document, ENTITY[v["document_id"]]))
                for coverage in v["coverages"]:
                    cn = ENTITY[v["id"] + "-" + coverage]
                    owners[str(cn)] = aggregate
                    g.add((vn, ISW.hasCoverage, cn))
                    g.add((cn, RDF.type, ISW.PurchasedCoverage))
                    g.add((cn, ISW.definition, ISW[f"concept/{coverage}"]))
                    g.add((cn, ISW.clause, ENTITY[v["document_id"] + "-" + coverage]))
        elif src["kind"] == "document":
            g.add((node, RDF.type, ISW.DocumentVersion))
            lit(g, node, ISW.sha256, digest(p["text"].encode("utf-8")))
            lit(g, node, ISW.validFrom, p["valid_from"], XSD.date)
            lit(g, node, ISW.language, p["language"])
            lit(g, node, ISW.textLength, len(p["text"]), XSD.integer)
            for clause in p["clauses"]:
                cn = ENTITY[p["id"] + "-" + clause["id"]]
                owners[str(cn)] = aggregate
                g.add((node, ISW.hasClause, cn))
                g.add((cn, RDF.type, ISW.Clause))
                lit(g, cn, ISW.start, clause["start"], XSD.integer)
                lit(g, cn, ISW.end, clause["end"], XSD.integer)
        else:
            case = cases[aggregate]
            g.add((node, RDF.type, ISW.Claim))
            g.add((node, ISW.policy, ENTITY[p["policy_id"]]))
            loss = ENTITY[p["loss_id"]]
            owners[str(loss)] = aggregate
            g.add((node, ISW.loss, loss))
            g.add((loss, RDF.type, ISW.LossEvent))
            lit(g, loss, ISW.sourceId, p["loss_id"])
            lit(g, loss, ISW.lossDate, p.get("loss_date"), XSD.date)
            for prop, val in [
                (ISW.country, p["country"]),
                (ISW.currency, p["currency"]),
                (ISW.status, p["status"]),
                (ISW.sourceCode, p["source_code"]),
            ]:
                lit(g, node, prop, val)
            # Jena canonicalizes decimal lexical forms. Preserve source spelling in the snapshot,
            # but use one canonical graph spelling so cross-store digest checks remain meaningful.
            try:
                numeric = Decimal(p["amount"])
                if not numeric.is_finite():
                    raise InvalidOperation
                amount = format(numeric.normalize(), "f")
                if "." not in amount:
                    amount += ".0"
                lit(g, node, ISW.amount, amount, XSD.decimal)
            except InvalidOperation:
                # Keep malformed monetary input inspectable; SHACL quarantines its string datatype.
                lit(g, node, ISW.amount, p["amount"])
            g.add((node, ISW.classification, ISW["concept/" + case["classification"]]))
            lit(g, node, ISW.ready, case["status"] == "sufficient", XSD.boolean)
            assignment = ENTITY[p["id"] + "-reporter"]
            g.add((node, ISW.hasRole, assignment))
            g.add((assignment, RDF.type, ISW.RoleAssignment))
            g.add((assignment, ISW.party, ENTITY[p["reporter"]["id"]]))
            lit(g, assignment, ISW.role, "reporter")
            g.add((assignment, ISW.context, node))
            policy = case["policy"]
            if policy and policy["id"] not in excluded:
                assignment = ENTITY[p["id"] + "-insured"]
                g.add((node, ISW.hasRole, assignment))
                g.add((assignment, RDF.type, ISW.RoleAssignment))
                g.add((assignment, ISW.party, ENTITY[policy["party"]["id"]]))
                lit(g, assignment, ISW.role, "insured")
                g.add((assignment, ISW.context, ENTITY[policy["id"]]))
            if p.get("mitigation"):
                m = ENTITY[p["mitigation"]["id"]]
                g.add((node, ISW.mitigation, m))
                g.add((m, RDF.type, CZ.MitigationAssessment))
            for finding in case["findings"]:
                fn = ENTITY["finding-" + digest(finding)[:16]]
                g.add((node, ISW.finding, fn))
                g.add((fn, RDF.type, ISW.ValidationFinding))
                lit(g, fn, ISW.message, finding["message"])
    for item in items:
        if item["case_scope"] in excluded:
            continue
        g = graphs[item["country_scope"]]
        node = ENTITY[item["evidence_id"]]
        owners[str(node)] = item["source_id"]
        g.add((ENTITY[item["case_scope"]], ISW.evidence, node))
        g.add((node, RDF.type, ISW.EvidenceAssertion))
        g.add((node, PROV.wasDerivedFrom, ENTITY[item["source_snapshot_id"]]))
        for support in item.get("supporting_sources", []):
            g.add((node, PROV.wasDerivedFrom, ENTITY[support["source_snapshot_id"]]))
        g.add((node, PROV.wasGeneratedBy, ENTITY[item["transformation_id"]]))
        for prop, value in [
            (ISW.text, item["text_or_value"]),
            (ISW.groupId, item["group_id"]),
            (ISW.locator, json_text(item["locator"])),
            (ISW.mappingRelease, release),
        ]:
            lit(g, node, prop, value)
        if item.get("cause"):
            g.add((ENTITY[item["case_scope"]], ISW.hasAssertion, node))
            g.add((node, ISW.cause, ISW["concept/" + item["cause"]]))
    return graphs, owners


def build(records, release, projection, root=SEMANTIC):
    cases = source_context(records, release, root)
    vocabulary = ontology(release, root)
    items = [
        item
        for case in cases.values()
        for item in evidence_for(case, records, release, projection, vocabulary)
    ]
    graphs, owners = _graphs(records, cases, items, release, projection, root=root)
    shape_graph = shapes(release, root)
    findings = []
    reports = {}
    excluded = set()
    for country, g in graphs.items():
        _, report, _ = validate(
            g,
            shacl_graph=shape_graph,
            inference="rdfs",
            meta_shacl=True,
            advanced=False,
            do_owl_imports=False,
            allow_infos=True,
            allow_warnings=True,
        )
        if not isinstance(report, Graph):
            raise TypeError("SHACL engine failed to return a validation graph")
        reports[country] = report.serialize(format="turtle")
        for node in report.subjects(RDF.type, SH.ValidationResult):
            shape = report.value(node, SH.sourceShape)
            parent = shape_graph.value(predicate=SH.property, object=shape)
            group = str(
                shape_graph.value(shape, ISW.status) or shape_graph.value(parent, ISW.status) or "structural"
            )
            focus = str(report.value(node, SH.focusNode))
            source_id = owners.get(focus)
            finding = {
                "focus_node": focus,
                "source_id": source_id,
                "country": country,
                "category": group,
                "path": str(report.value(node, SH.resultPath) or ""),
                "shape": str(shape),
                "severity": str(report.value(node, SH.resultSeverity)),
                "message": str(report.value(node, SH.resultMessage)),
                "remediation": "Correct the original source or record an evidence-backed steward decision",
            }
            findings.append(finding)
            if group == "structural" and source_id:
                excluded.add(source_id)
    for case in cases.values():
        documents = {v["document_id"] for v in case["policy_versions"]}
        dependencies = {case["id"], case["claim"]["policy_id"], *documents}
        case["findings"] = [f for f in findings if f["source_id"] in dependencies]
        if documents & excluded:
            case["missing"].append("The applicable contract document is structurally invalid and quarantined")
        case["quarantined"] = case["id"] in excluded
        if case["claim"]["policy_id"] in excluded:
            case["policy_versions"] = []
            case["missing"].append("The current policy source is quarantined by structural validation")
        if case["quarantined"]:
            case["status"] = "quarantined"
        elif case["conflicts"]:
            case["status"] = "conflicted"
        elif case["missing"] or case["findings"]:
            case["status"] = "incomplete"
        else:
            case["status"] = "sufficient"
    items = [
        item
        for case in cases.values()
        for item in evidence_for(case, records, release, projection, vocabulary)
        if item["source_id"] not in excluded
    ]
    graphs, _ = _graphs(records, cases, items, release, projection, excluded, root)
    inferred = {}
    for country, g in graphs.items():
        expanded = Graph() + g
        DeductiveClosure(RDFS_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(expanded)
        # owlrl can materialize generalized RDF with literal subjects. RDF stores accept
        # standard RDF only; those datatype bookkeeping triples are not application facts.
        inferred[country] = Graph()
        for triple in expanded - g:
            if not isinstance(triple[0], Literal):
                inferred[country].add(triple)
    return cases, items, graphs, inferred, findings, reports
