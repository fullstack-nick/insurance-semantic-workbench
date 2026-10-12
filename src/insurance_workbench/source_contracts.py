"""Transport structure is checked here; semantic validity belongs to SHACL."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Z][A-Za-z0-9-]{1,100}$")]


class SourceObject(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Identifier
    country: Literal["AT", "CZ"]


class Party(BaseModel):
    id: Identifier
    name: str


class Observation(BaseModel):
    id: str
    by: str
    cause: Literal["water-damage", "pipe-leakage", "surface-flooding"]
    text: str


class Mitigation(BaseModel):
    id: Identifier
    text: str


class Claim(SourceObject):
    policy_id: Identifier
    loss_id: Identifier
    loss_date: date | None
    status: str
    amount: str
    currency: str
    source_code: str
    reporter: Party
    observations: list[Observation]
    mitigation: Mitigation | None = None
    identity_candidate: Identifier | None = None


class PolicyVersion(BaseModel):
    id: Identifier
    valid_from: date
    valid_to: date | None = None
    document_id: Identifier
    coverages: list[str]


class Policy(SourceObject):
    property_country: Literal["AT", "CZ"]
    product: str
    party: Party
    offered_coverages: list[str]
    versions: list[PolicyVersion]

    @field_validator("versions")
    @classmethod
    def unique_versions(cls, value):
        if len({v.id for v in value}) != len(value):
            raise ValueError("Policy version IDs must be unique within a source snapshot")
        return value


class Clause(BaseModel):
    id: str
    start: int
    end: int
    coverage: str


class Document(SourceObject):
    document_id: Identifier
    text: str
    language: Literal["en", "de", "cs"]
    valid_from: date
    valid_to: date | None = None
    clauses: list[Clause]


CONTRACTS = {"claim": Claim, "policy": Policy, "document": Document}
