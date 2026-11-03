"""The G/V declaration scheme: levels, keys and the completeness rules."""
from __future__ import annotations

from dataclasses import dataclass, field

GENERATION = {
    "G0": "Human",
    "G1": "AI-assisted",
    "G2": "AI-generated",
    "G3": "AI-autonomous",
}
VERIFICATION = {
    "V0": "Human",
    "V1": "Independent agent, same model",
    "V2": "Independent agent, different model",
    "V3": "Human + independent agent",
}

# Canonical key names. They are identical to the git trailers used in pull requests.
GEN, VER, ASSISTED, VERIFIED, TESTED = (
    "AI-Generation",
    "AI-Verification",
    "Assisted-by",
    "Verified-by",
    "Tested-by",
)
SINGLE_KEYS = (GEN, VER)
LIST_KEYS = (ASSISTED, VERIFIED, TESTED)
KEYS = SINGLE_KEYS + LIST_KEYS


def canonical_key(name: str) -> str | None:
    """Return the canonical spelling of a declaration key (case-insensitive), or None."""
    for key in KEYS:
        if key.lower() == name.strip().lower():
            return key
    return None


@dataclass
class Declaration:
    """The resolved declaration of one file."""

    generation: str | None = None
    verification: str | None = None
    assisted_by: tuple[str, ...] = ()
    verified_by: tuple[str, ...] = ()
    tested_by: tuple[str, ...] = ()
    source: str = "none"  # e.g. 'AIDECL.toml [2]', 'inline', 'none'
    problems: list[str] = field(default_factory=list)  # parse problems found while reading it

    @classmethod
    def from_mapping(cls, values: dict, source: str) -> "Declaration":
        def as_tuple(v):
            if v is None:
                return ()
            if isinstance(v, str):
                v = [v]
            return tuple(s.strip() for s in v if str(s).strip())

        return cls(
            generation=(values.get(GEN) or None),
            verification=(values.get(VER) or None),
            assisted_by=as_tuple(values.get(ASSISTED)),
            verified_by=as_tuple(values.get(VERIFIED)),
            tested_by=as_tuple(values.get(TESTED)),
            source=source,
        )

    def as_dict(self) -> dict:
        return {
            GEN: self.generation,
            VER: self.verification,
            ASSISTED: list(self.assisted_by),
            VERIFIED: list(self.verified_by),
            TESTED: list(self.tested_by),
            "source": self.source,
        }


def validate(d: Declaration) -> list[str]:
    """Return the rule violations of a declaration (empty list = valid)."""
    errors = list(d.problems)
    if d.source == "none":
        return ["no declaration (not matched by AIDECL.toml and no inline tags)"]
    if d.generation is None:
        errors.append(f"missing {GEN}")
    elif d.generation not in GENERATION:
        errors.append(f"invalid {GEN} '{d.generation}' (use G0, G1, G2 or G3)")
    if d.verification is None:
        errors.append(f"missing {VER}")
    elif d.verification not in VERIFICATION:
        errors.append(f"invalid {VER} '{d.verification}' (use V0, V1, V2 or V3)")

    if d.generation in ("G1", "G2", "G3") and not d.assisted_by:
        errors.append(f"{d.generation} needs {ASSISTED} (tool and model)")
    if d.generation == "G0" and d.assisted_by:
        errors.append(f"G0 means no AI was used, but {ASSISTED} is set")
    if d.verification in ("V1", "V2", "V3") and not d.verified_by:
        errors.append(f"{d.verification} needs {VERIFIED} (verifying model and session)")
    if d.verification in ("V0", "V3") and not d.tested_by:
        errors.append(f"{d.verification} needs {TESTED} (the human who tested)")
    return errors
