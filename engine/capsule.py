"""
ONE ENGINE — capsule envelope.

From Pixel Capsule's engine pattern (authorized reuse): the output is a
SEALED artifact — versioned, hashed, self-describing — not a printout.
The capsule carries: engine version, input hash, stage verdicts, provenance
log, honesty marks, and the markings ([SYNTH] [POLICY] [UNMEASURABLE]).

Verify with capsule_verify(): recompute the hash, compare.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

ENGINE_VERSION = 1
MAGIC = "ONE1"


@dataclass
class Capsule:
    magic: str
    version: int
    created_utc: str
    input_hash: str
    stages: List[Dict[str, Any]]
    verdict: Dict[str, Any]
    provenance: List[Dict[str, Any]]
    marks: List[str]
    payload_hash: str = ""

    def seal(self) -> "Capsule":
        body = json.dumps(asdict(self), sort_keys=True).encode()
        self.payload_hash = hashlib.sha256(body).hexdigest()
        return self

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _hash_input(data: Any) -> str:
    """Four's Break 1 fix: hash the CONTENT, not its length.
    numpy arrays -> shape + raw bytes; everything else -> canonical JSON."""
    import numpy as _np
    h = hashlib.sha256()
    if isinstance(data, _np.ndarray):
        h.update(str(data.shape).encode())
        h.update(data.tobytes())
    else:
        h.update(json.dumps(data, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def capsule_seal(input_data: Any, stages: List[Dict[str, Any]],
                 verdict: Dict[str, Any], provenance: List[Dict[str, Any]],
                 marks: List[str]) -> Capsule:
    """Seal an engine run into a verifiable capsule."""
    ih = _hash_input(input_data)
    cap = Capsule(
        magic=MAGIC, version=ENGINE_VERSION,
        created_utc=datetime.now(timezone.utc).isoformat(),
        input_hash=ih, stages=stages, verdict=verdict,
        provenance=provenance, marks=marks)
    return cap.seal()


def capsule_verify(cap_json: str) -> bool:
    """Recompute the payload hash; True iff the capsule is intact."""
    d = json.loads(cap_json)
    d["payload_hash"] = ""  # seal() hashed with the field present-but-empty
    body = json.dumps(d, sort_keys=True).encode()
    return hashlib.sha256(body).hexdigest() == json.loads(cap_json)["payload_hash"]
