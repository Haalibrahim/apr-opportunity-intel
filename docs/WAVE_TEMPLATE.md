# Wave Configuration Template

Every wave is a self-contained JSON file in the `waves/` directory. This document explains each field and how to create a new wave.

The gold-standard example is `wave4_computational.json` (designed by Raff).

---

## Required fields

### Metadata

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, e.g. `wave4_computational` |
| `name` | string | Human-readable name, e.g. "Computational & Systems Analysis" |
| `version` | string | Semantic version, e.g. "1.0" |
| `owner` | string | Who maintains this wave |
| `color` | string | Hex color for UI display, e.g. "#7F77DD" |
| `description` | string | 1-2 sentence description of what this wave covers |

### Scope

Defines what is **in** and **out** of this wave's focus.

```json
"scope": {
  "included": [
    "Topic that belongs in this wave",
    "Another relevant topic"
  ],
  "excluded": [
    "Topic that should NOT be picked up",
    "Another exclusion"
  ]
}
```

### Ranking rules

How the scanner prioritizes results within this wave.

```json
"ranking_rules": {
  "primary_filter": {
    "name": "Name of the filter",
    "optimal": "Description of ideal match",
    "minimum": "Minimum threshold for inclusion",
    "exclude_below": "What gets filtered out"
  },
  "funding_preference": {
    "high_priority": "$500K–$1M",
    "lower_priority": "<$500K unless strategic",
    "deprioritized": ">$1M unless strongly aligned"
  },
  "interdisciplinarity": {
    "preferred": "2–3 tightly coupled disciplines",
    "avoid": "Overly diffuse consortia",
    "exclude": "No clear computational/analytical core"
  }
}
```

### Sources

Each source is an agency, foundation, or platform the scanner should check.

```json
"sources": [
  {
    "name": "Agency or Foundation Name",
    "type": "Federal | Foundation | International | Conference | Academic | Corporate",
    "url": "primary website or portal",
    "search_for": "What to look for at this source"
  }
]
```

### Search queries

Pre-built search queries the scanner will use with web search.

```json
"search_queries": [
  "NSF computational social science grant 2026",
  "DARPA BAA AI systems 2026 open"
]
```

---

## Optional fields

### Optional sources

Sources that are nice-to-have but not critical.

```json
"optional_sources": [
  {"name": "Conference", "url": "conf.org", "search_for": "Workshop calls"}
]
```

### ARPA detection module

Lightweight flag for rapid-cycle defense/intelligence solicitations.

```json
"arpa_detection": {
  "enabled": true,
  "watch": ["DARPA BAAs", "IARPA solicitations", "ARPA-H calls"]
}
```

---

## Checklist for a new wave

- [ ] Unique `id` that won't collide with existing waves
- [ ] Clear `scope.included` (at least 5 topics)
- [ ] Clear `scope.excluded` (at least 3 exclusions)
- [ ] Ranking rules with primary filter, funding preference, and interdisciplinarity
- [ ] At least 5 sources with name, type, url, and search_for
- [ ] At least 5 search queries
- [ ] Test by running: `python scanner.py --wave YOUR_WAVE_ID`
