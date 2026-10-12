"""Build reviewable Turtle and fixed queries from this authored semantic catalog."""

import hashlib
import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, SKOS, XSD, Graph, Literal, Namespace

ROOT = Path(__file__).resolve().parent
ISW = Namespace("https://example.org/isw/term/")
CZ = Namespace("https://example.org/isw/cz/")
SH = Namespace("http://www.w3.org/ns/shacl#")
PROV = Namespace("http://www.w3.org/ns/prov#")
LAYERS = {
    "enterprise": [
        "Party",
        "Person",
        "Organization",
        "RoleAssignment",
        "Contract",
        "Asset",
        "Document",
        "SourceRecord",
    ],
    "domain": [
        "Policy",
        "PolicyVersion",
        "Product",
        "CoverageDefinition",
        "PurchasedCoverage",
        "Clause",
        "Claim",
        "LossEvent",
        "Assessment",
        "DocumentVersion",
        "SourceSnapshot",
    ],
    "country": ["MitigationAssessment"],
    "usecase": [
        "EvidenceAssertion",
        "EvidenceBundle",
        "ReviewRequest",
        "ReviewBrief",
        "MissingEvidence",
        "MappingReview",
        "ValidationFinding",
        "SemanticRelease",
        "ProjectionSnapshot",
        "ConsumerDependency",
    ],
}
PROPERTIES = {
    "sourceId": (None, None),
    "country": (None, None),
    "propertyCountry": ("Policy", None),
    "hasVersion": ("Policy", "PolicyVersion"),
    "policy": ("Claim", "Policy"),
    "validFrom": (None, None),
    "validTo": (None, None),
    "hasCoverage": ("PolicyVersion", "PurchasedCoverage"),
    "definition": ("PurchasedCoverage", "CoverageDefinition"),
    "document": ("PolicyVersion", "DocumentVersion"),
    "hasClause": ("DocumentVersion", "Clause"),
    "clause": ("PurchasedCoverage", "Clause"),
    "loss": ("Claim", "LossEvent"),
    "lossDate": ("LossEvent", None),
    "status": (None, None),
    "amount": ("Claim", None),
    "currency": ("Claim", None),
    "hasRole": (None, "RoleAssignment"),
    "party": ("RoleAssignment", "Party"),
    "role": ("RoleAssignment", None),
    "context": ("RoleAssignment", None),
    "hasAssertion": ("Claim", "EvidenceAssertion"),
    "cause": ("EvidenceAssertion", None),
    "assertedBy": ("EvidenceAssertion", None),
    "text": (None, None),
    "sha256": (None, None),
    "sourceSnapshot": (None, "SourceSnapshot"),
    "locator": (None, None),
    "mappingRelease": (None, None),
    "release": (None, "SemanticRelease"),
    "projection": (None, "ProjectionSnapshot"),
    "transformation": (None, None),
    "language": ("DocumentVersion", None),
    "start": ("Clause", None),
    "end": ("Clause", None),
    "textLength": ("DocumentVersion", None),
    "owner": (None, None),
    "mappingTarget": ("MappingReview", None),
    "mappingStrength": ("MappingReview", None),
    "sourceCode": ("Claim", None),
    "classification": ("Claim", None),
    "ready": ("Claim", None),
    "finding": ("Claim", "ValidationFinding"),
    "message": ("ValidationFinding", None),
    "mitigation": ("Claim", "Assessment"),
    "evidence": ("Claim", "EvidenceAssertion"),
    "groupId": ("EvidenceAssertion", None),
    "dependsOn": ("ConsumerDependency", None),
    "crosswalk": (None, None),
    "namespace": (None, None),
    "predecessor": ("SemanticRelease", "SemanticRelease"),
    "evidenceBundle": ("ReviewBrief", "EvidenceBundle"),
    "generatedBy": ("ReviewBrief", "ReviewRequest"),
    "offeredCoverage": ("Product", "CoverageDefinition"),
    "product": ("Policy", "Product"),
}
TERMS = [
    ("water-damage", "Water damage", "Wasserschaden", "Škoda vodou"),
    ("pipe-leakage", "Pipe leakage", "Rohrleckage", "Únik vody z potrubí"),
    ("surface-flooding", "Surface flooding", "Oberflächenüberflutung", "Povrchová záplava"),
    ("insured", "Insured party", "Versicherte Person", "Pojištěná osoba"),
    ("reporter", "Reporter", "Meldende Person", "Oznamovatel"),
    ("assessor", "Assessor", "Begutachtung", "Posuzovatel"),
    ("open", "Open", "Offen", "Otevřeno"),
    ("reviewed", "Reviewed", "Geprüft", "Zkontrolováno"),
    ("contract", "Contract terms", "Vertragsbedingungen", "Smluvní podmínky"),
    ("report", "Assessment report", "Gutachten", "Posudek"),
    ("photos", "Photographs", "Fotos", "Fotografie"),
    ("invoice", "Invoice", "Rechnung", "Faktura"),
    ("pipe", "Pipe cover", "Rohrdeckung", "Krytí potrubí"),
    ("flood", "Flood cover", "Überflutungsdeckung", "Krytí záplavy"),
    ("deductible", "Deductible", "Selbstbehalt", "Spoluúčast"),
    ("duties", "Evidence duties", "Nachweispflichten", "Povinné podklady"),
    ("mitigation", "Mitigation", "Schadenminderung", "Zmírnění škody"),
    ("sufficient", "Sufficient evidence", "Ausreichende Nachweise", "Dostatečné podklady"),
    ("incomplete", "Incomplete", "Unvollständig", "Neúplné"),
    ("conflicted", "Conflicting evidence", "Widersprüchliche Nachweise", "Rozporné podklady"),
    ("quarantined", "Quarantined", "Zurückgestellt", "V karanténě"),
    ("approved", "Approved", "Freigegeben", "Schváleno"),
    ("proposed", "Proposed", "Vorgeschlagen", "Navrženo"),
    ("rejected", "Rejected", "Abgelehnt", "Zamítnuto"),
    ("broad", "Broad mapping", "Breite Zuordnung", "Široké mapování"),
    ("exact", "Exact mapping", "Exakte Zuordnung", "Přesné mapování"),
    ("close", "Close mapping", "Nahe Zuordnung", "Blízké mapování"),
    ("unknown", "Unknown cause", "Unbekannte Ursache", "Neznámá příčina"),
    ("current", "Current", "Aktuell", "Aktuální"),
    ("stale", "Stale", "Veraltet", "Zastaralé"),
    ("historical", "Historical", "Historisch", "Historické"),
    ("household", "Household", "Haushalt", "Domácnost"),
    ("building", "Building", "Gebäude", "Budova"),
    ("contents", "Contents", "Hausrat", "Vybavení"),
    ("customer", "Customer", "Kunde", "Zákazník"),
    ("steward", "Steward", "Fachverantwortung", "Správce pojmů"),
    ("architect", "Architect", "Architektur", "Architekt"),
    ("handler", "Claim handler", "Schadenbearbeitung", "Likvidátor"),
    ("source-record", "Source record", "Quelldatensatz", "Zdrojový záznam"),
    ("clause", "Clause", "Klausel", "Ustanovení"),
]


def graph():
    g = Graph()
    for prefix, ns in [("isw", ISW), ("cz", CZ), ("sh", SH), ("prov", PROV), ("skos", SKOS), ("owl", OWL)]:
        g.bind(prefix, ns)
    return g


def build():
    for layer, classes in LAYERS.items():
        g = graph()
        module = ISW[f"module/{layer}"]
        g.add((module, RDF.type, OWL.Ontology))
        g.add((module, OWL.versionInfo, Literal("1.0.0")))
        if layer != "enterprise":
            g.add((module, OWL.imports, ISW["module/enterprise" if layer == "domain" else "module/domain"]))
        for name in classes:
            term = CZ[name] if layer == "country" else ISW[name]
            g.add((term, RDF.type, OWL.Class))
            g.add((term, RDFS.label, Literal(name, lang="en")))
            g.add((term, ISW.owner, Literal(f"Fictional {layer} stewardship")))
        if layer == "enterprise":
            for child in ["Person", "Organization"]:
                g.add((ISW[child], RDFS.subClassOf, ISW.Party))
        if layer == "domain":
            for child, parent in [
                ("Policy", "Contract"),
                ("DocumentVersion", "Document"),
                ("SourceSnapshot", "SourceRecord"),
            ]:
                g.add((ISW[child], RDFS.subClassOf, ISW[parent]))
        if layer == "country":
            g.add((CZ.MitigationAssessment, RDFS.subClassOf, ISW.Assessment))
        if layer == "usecase":
            for name, (domain, range_) in PROPERTIES.items():
                term = ISW[name]
                g.add((term, RDF.type, RDF.Property))
                if domain:
                    g.add((term, RDFS.domain, ISW[domain]))
                if range_:
                    g.add((term, RDFS.range, ISW[range_]))
            g.add((ISW.evidence, RDFS.subPropertyOf, ISW.hasAssertion))
        g.serialize(ROOT / f"{layer}.ttl", format="turtle")
    for version in ["1.0.0", "2.0.0"]:
        directory = ROOT / version
        directory.mkdir(exist_ok=True)
        g = graph()
        for slug, en, de, cs in TERMS:
            if version == "1.0.0" and slug in ["pipe-leakage", "surface-flooding"]:
                continue
            term = ISW[f"concept/{slug}"]
            g.add((term, RDF.type, SKOS.Concept))
            for lang, label in [("en", en), ("de", de), ("cs", cs)]:
                g.add((term, SKOS.prefLabel, Literal(label, lang=lang)))
            g.add(
                (
                    term,
                    SKOS.definition,
                    Literal(
                        f"Fictional workbench concept: {en.lower()}. No legal or insurer-specific meaning is implied.",
                        lang="en",
                    ),
                )
            )
            g.add(
                (
                    term,
                    SKOS.scopeNote,
                    Literal("Only the invented demonstration operating profiles apply.", lang="en"),
                )
            )
            g.add((term, ISW.owner, Literal("Fictional domain steward")))
            g.add((term, ISW.status, Literal("approved")))
            if slug in ["pipe-leakage", "surface-flooding"]:
                g.add((term, SKOS.broader, ISW["concept/water-damage"]))
        g.serialize(directory / "vocabulary.ttl", format="turtle")
        mappings = {
            "release": version,
            "codes": {
                "AT:WD": {"target": "water-damage", "strength": "exact", "owner": "AT steward"},
                "CZ:VODA": {"target": "water-damage", "strength": "exact", "owner": "CZ steward"},
            },
            "narrowing_requires_assertion": True,
            "narrowing_enabled": version == "2.0.0",
        }
        (directory / "mappings.json").write_text(json.dumps(mappings, indent=2), encoding="utf-8")
    build_shapes()
    build_queries()
    consumers = []
    for i in range(1, 19):
        consumers.append(
            {
                "id": f"CQ{i:02d}",
                "kind": "query",
                "terms": ["Claim", "PolicyVersion", "classification"]
                if i in [1, 7, 16, 17]
                else ["EvidenceAssertion", "sourceSnapshot"],
                "path": f"queries/CQ{i:02d}.rq",
            }
        )
    consumers.extend(
        [
            {"id": n, "kind": k, "terms": terms}
            for n, k, terms in [
                ("source-peril-map", "mapping", ["classification", "cause"]),
                ("readiness-v2", "shape", ["classification", "ready"]),
                ("claim-fact-card", "template", ["Claim", "classification", "policy"]),
                ("case-header", "ui", ["PolicyVersion", "ready"]),
                ("get_case_context", "agent", ["Claim", "classification"]),
                ("retrieval-v1", "retrieval", ["evidence", "clause"]),
            ]
        ]
    )
    (ROOT / "consumers.json").write_text(json.dumps(consumers, indent=2), encoding="utf-8")
    catalog = {
        "profile": "RDFS",
        "network_imports": False,
        "modules": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in ROOT.glob("*.ttl")},
    }
    (ROOT / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")


def build_shapes():
    g = graph()

    def node(name, target, group):
        n = ISW[f"shape/{name}"]
        g.add((n, RDF.type, SH.NodeShape))
        g.add((n, SH.targetClass, target))
        g.add((n, ISW.status, Literal(group)))
        return n

    def prop(n, name, path, minimum=0, datatype=None, values=None, message=None):
        p = ISW[f"shape/{name}"]
        g.add((n, SH.property, p))
        g.add((p, SH.path, path))
        if minimum:
            g.add((p, SH.minCount, Literal(minimum)))
        if datatype:
            g.add((p, SH.datatype, datatype))
        if values:
            from rdflib.collection import Collection

            head = ISW[f"shape/{name}/values"]
            Collection(g, head, [Literal(v) for v in values])
            g.add((p, SH["in"], head))
        if message:
            g.add((p, SH.message, Literal(message)))
        return p

    def sparql(n, name, query, message):
        q = ISW[f"shape/{name}/query"]
        g.add((n, SH.sparql, q))
        g.add((q, SH.message, Literal(message)))
        g.add((q, SH.select, Literal("PREFIX isw: <https://example.org/isw/term/>\n" + query)))

    n = node("SourceIdentity", ISW.SourceSnapshot, "structural")
    prop(n, "SourceId", ISW.sourceId, 1)
    n = node("ClaimReferences", ISW.Claim, "structural")
    prop(n, "PolicyRef", ISW.policy, 1)
    prop(n, "LossRef", ISW.loss, 1)
    n = node("CrosswalkUnique", ISW.SourceRecord, "structural")
    sparql(
        n,
        "CrosswalkUnique",
        "SELECT $this WHERE {$this isw:namespace ?ns; isw:sourceId ?id. ?other isw:namespace ?ns; isw:sourceId ?id. FILTER(?other != $this)}",
        "Source identity is not unique in its namespace",
    )
    n = node("VersionPeriod", ISW.PolicyVersion, "structural")
    prop(n, "From", ISW.validFrom, 1, XSD.date)
    n = node("PeriodOrder", ISW.PolicyVersion, "structural")
    sparql(
        n,
        "PeriodOrder",
        "SELECT $this WHERE {$this isw:validFrom ?a; isw:validTo ?b. FILTER(?a >= ?b)}",
        "Policy period must end after its start",
    )
    n = node("NoOverlap", ISW.PolicyVersion, "structural")
    sparql(
        n,
        "NoOverlap",
        "SELECT $this WHERE {?p isw:hasVersion $this, ?other. $this isw:validFrom ?a. ?other isw:validFrom ?b. OPTIONAL {$this isw:validTo ?ae} OPTIONAL {?other isw:validTo ?be} FILTER($this != ?other && (!BOUND(?ae) || ?b < ?ae) && (!BOUND(?be) || ?a < ?be))}",
        "Policy versions overlap; select no arbitrary latest version",
    )
    n = node("PurchasedCoverage", ISW.PurchasedCoverage, "structural")
    prop(n, "Definition", ISW.definition, 1)
    prop(n, "CoverageClause", ISW.clause, 1)
    n = node("LossDate", ISW.LossEvent, "readiness")
    prop(
        n,
        "LossDateValue",
        ISW.lossDate,
        1,
        XSD.date,
        message="Loss date is required to select historical terms",
    )
    n = node("ClaimValues", ISW.Claim, "structural")
    prop(n, "Currency", ISW.currency, 1, values=["EUR", "CZK"], message="Use the source currency EUR or CZK")
    prop(n, "Amount", ISW.amount, 1, XSD.decimal)
    prop(n, "Status", ISW.status, 1, values=["open", "reviewed"])
    n = node("LossIdentity", ISW.LossEvent, "structural")
    prop(n, "LossId", ISW.sourceId, 1)
    n = node("DocumentHash", ISW.DocumentVersion, "structural")
    p = prop(n, "DocHash", ISW.sha256, 1)
    g.add((p, SH.pattern, Literal("^[0-9a-f]{64}$")))
    n = node("ClauseBounds", ISW.Clause, "structural")
    prop(n, "Start", ISW.start, 1, XSD.integer)
    prop(n, "End", ISW.end, 1, XSD.integer)
    sparql(
        n,
        "ClauseBounds",
        "SELECT $this WHERE {$this isw:start ?s; isw:end ?e. ?doc isw:hasClause $this; isw:textLength ?n. FILTER(?s < 0 || ?e <= ?s || ?e > ?n)}",
        "Clause offsets must fit the immutable document text",
    )
    n = node("DocumentPeriod", ISW.DocumentVersion, "structural")
    prop(n, "DocumentFrom", ISW.validFrom, 1, XSD.date)
    n = node("AssertionProvenance", ISW.EvidenceAssertion, "structural")
    prop(n, "DerivedFrom", PROV.wasDerivedFrom, 1)
    prop(n, "EvidenceLocator", ISW.locator, 1)
    n = node("SourceActivity", ISW.SourceSnapshot, "structural")
    prop(n, "GeneratedBy", PROV.wasGeneratedBy, 1)
    n = node("Labels", SKOS.Concept, "structural")
    p = prop(n, "PreferredLabel", SKOS.prefLabel, 1)
    g.add((p, SH.uniqueLang, Literal(True)))
    n = node("Mapping", ISW.MappingReview, "structural")
    prop(n, "Target", ISW.mappingTarget, 1)
    prop(n, "Strength", ISW.mappingStrength, 1, values=["exact", "close", "broad"])
    prop(n, "MappingStatus", ISW.status, 1)
    n = node("ConflictingCause", ISW.Claim, "readiness")
    sparql(
        n,
        "ConflictingCause",
        "SELECT $this WHERE {$this isw:hasAssertion ?x, ?y. ?x isw:cause ?a. ?y isw:cause ?b. FILTER(?a != ?b)}",
        "Sources disagree about the cause; retain both assertions",
    )
    n = node("ATApplicability", ISW.Claim, "readiness")
    sparql(
        n,
        "ATApplicability",
        "SELECT $this WHERE {$this isw:country 'AT'. FILTER NOT EXISTS {$this isw:evidence ?e. ?e isw:groupId ?g. FILTER(CONTAINS(?g,'clause-pipe'))}}",
        "AT profile requires the applicable purchased pipe clause",
    )
    n = node("CZMitigation", ISW.Claim, "readiness")
    sparql(
        n,
        "CZMitigation",
        "SELECT $this WHERE {$this isw:country 'CZ'. FILTER NOT EXISTS {$this isw:mitigation ?m}}",
        "CZ profile requires a mitigation assessment",
    )
    g.serialize(ROOT / "shapes.ttl", format="turtle")
    stricter = graph()
    n = ISW["shape/SpecificCause"]
    stricter.add((n, RDF.type, SH.NodeShape))
    stricter.add((n, SH.targetClass, ISW.Claim))
    stricter.add((n, ISW.status, Literal("readiness")))
    q = ISW["shape/SpecificCause/query"]
    stricter.add((n, SH.sparql, q))
    stricter.add(
        (
            q,
            SH.message,
            Literal(
                "Release 2 requires source-supported specific cause; broad water damage remains unresolved"
            ),
        )
    )
    stricter.add(
        (
            q,
            SH.select,
            Literal(
                "PREFIX isw: <https://example.org/isw/term/> SELECT $this WHERE {$this isw:classification <https://example.org/isw/term/concept/water-damage>}"
            ),
        )
    )
    stricter.serialize(ROOT / "2.0.0/readiness.ttl", format="turtle")


def build_queries():
    directory = ROOT / "queries"
    directory.mkdir(exist_ok=True)
    patterns = [
        "?case isw:policy ?policy; isw:loss/isw:lossDate ?date. ?policy isw:hasVersion ?version. ?version isw:validFrom ?from. OPTIONAL {?version isw:validTo ?to} FILTER(?from <= ?date && (!BOUND(?to) || ?date < ?to))",
        "?case isw:policy/isw:hasVersion ?version; isw:loss/isw:lossDate ?date. ?version isw:hasCoverage ?coverage; isw:validFrom ?from. OPTIONAL {?version isw:validTo ?to} FILTER(?from <= ?date && (!BOUND(?to) || ?date < ?to)) ?coverage isw:definition ?definition.",
        '?case isw:evidence ?evidence. ?evidence isw:groupId ?group; isw:text ?text. FILTER(CONTAINS(?group,"clause-"))',
        "?case isw:hasRole ?assignment. ?assignment isw:party ?party; isw:role ?role; isw:context ?context.",
        "?case isw:loss ?loss. ?claim isw:loss ?loss.",
        "?case isw:finding ?finding. ?finding isw:message ?message.",
        "?case isw:sourceCode ?code; isw:classification ?concept. FILTER(?concept = isw:concept/water-damage)",
        "?case isw:hasAssertion ?a, ?b. ?a isw:cause ?x; isw:text ?first. ?b isw:cause ?y; isw:text ?second. FILTER(?x != ?y)",
        "?case isw:evidence ?evidence. ?evidence prov:wasDerivedFrom ?source; isw:locator ?locator; isw:mappingRelease ?mapping. ?source isw:sha256 ?hash.",
        "?case isw:policy ?policy; isw:loss/isw:lossDate ?date. ?policy isw:hasVersion ?version. ?version isw:validFrom ?from; isw:document ?document. OPTIONAL {?version isw:validTo ?to} FILTER(?from <= ?date && (!BOUND(?to) || ?date < ?to))",
        "?concept a skos:Concept; skos:prefLabel ?label. OPTIONAL {?concept skos:broader ?broader}",
        "?case isw:country ?profile; isw:policy ?policy. ?policy isw:propertyCountry ?propertyCountry. OPTIONAL {?case isw:mitigation ?mitigation}",
        "?case isw:hasRole/isw:party ?party. ?party isw:crosswalk ?approvedIdentity. ?approvedIdentity isw:status 'approved'.",
        "?case isw:policy ?policy. ?policy a isw:Contract.",
        "?consumer a isw:ConsumerDependency; isw:dependsOn ?term.",
        "?release a isw:SemanticRelease. OPTIONAL {?release isw:predecessor ?predecessor} ?case isw:classification ?classification; isw:ready ?ready.",
        "",
        "?brief a isw:ReviewBrief; isw:projection ?projection; isw:release ?release; isw:evidenceBundle ?bundle.",
    ]
    manifest = []
    prefixes = "PREFIX isw: <https://example.org/isw/term/>\nPREFIX prov: <http://www.w3.org/ns/prov#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
    for i, pattern in enumerate(patterns, 1):
        if i == 7:
            pattern = pattern.replace(
                "isw:concept/water-damage", "<https://example.org/isw/term/concept/water-damage>"
            )
        query = (
            prefixes
            + "SELECT DISTINCT * WHERE { VALUES ?case { <$CASE> } GRAPH <$GRAPH> { "
            + pattern
            + " } } LIMIT 100"
        )
        if i == 11:
            query = query.replace("LIMIT 100", "LIMIT 150")
        if i == 14:
            query = (
                prefixes
                + "SELECT ?policy FROM <$GRAPH> FROM <$INFERRED_GRAPH> WHERE { <$CASE> isw:policy ?policy. ?policy a isw:Contract } LIMIT 100"
            )
        if i == 17:
            query = (
                prefixes
                + """SELECT ?country ?ready (COUNT(?claim) AS ?count) WHERE {
{ GRAPH <$GRAPH> { ?claim a isw:Claim; isw:country ?country; isw:ready ?ready } }
UNION { SERVICE <http://fuseki-cz:3030/ds/query> { GRAPH <$OTHER_GRAPH> { ?claim a isw:Claim; isw:country ?country; isw:ready ?ready } } }
} GROUP BY ?country ?ready ORDER BY ?country ?ready"""
            )
        (directory / f"CQ{i:02d}.rq").write_text(query, encoding="utf-8")
        manifest.append(
            {
                "id": f"CQ{i:02d}",
                "path": f"queries/CQ{i:02d}.rq",
                "parameters": ["case", "graph"],
                "scope": "pinned projection",
                "fixture": "CLM-AT-001" if i != 8 else "CLM-AT-005",
                "expected": "explicit empty until a brief is saved"
                if i == 18
                else "fixtures/competency-expectations.json",
            }
        )
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build()
