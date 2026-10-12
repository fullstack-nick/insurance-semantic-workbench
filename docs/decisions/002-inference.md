# 002 — Explicit RDFS and separate validation profiles

Materialize the bounded RDFS profile with RDFLib/owlrl and retain asserted/inferred graphs separately. This demonstrates class/property implications without claiming complete OWL reasoning. Local catalog checksums control ontology composition; external imports and SHACL-JS are disabled.

SHACL structural violations quarantine the affected aggregate and dependent context. Readiness findings preserve accepted but incomplete/conflicting cases. Release 2 deliberately tightens readiness for broad causes while keeping broad water damage a valid concept. Reports must come from a successful engine run; engine errors fail publication.

Jena normalizes RDF decimals, so graph generation uses canonical lexical forms while original source strings remain intact. Generalized RDFS triples with literal subjects are excluded from standard RDF publication.
