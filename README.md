# Agentic Systems Engineering: Code Repository

Companion code for *Agentic Systems Engineering: Building AI Agents That Actually Work in Production*, by Adrian Morgan Sebuliba.

This repository contains the book's reference implementation only: two complete, tested systems (an SRE Agent and a Document Intelligence Agent) demonstrating every pattern the book covers, plus their test suite and live smoke test scripts. It does not contain the book's text.

## Getting started

```
git clone https://github.com/IAgenticc/Agentic-Book.git
cd Agentic-Book/reference
pip install -e ".[dev]"
pytest -v
```

See [`reference/README.md`](reference/README.md) for the full layout, chapter-to-module map, how to run against real models and real databases, and the real bugs this code found along the way.

## License

MIT, see [`LICENSE`](LICENSE).
