"""Shared core between the SRE Agent and Document Intelligence Agent
reference implementations. Currently just the model interface (Chapter
26's Model Fallback), since that's the one piece both systems need
identically -- the rest of each system's patterns are specific enough
to its own domain to stay in sre_agent/ and document_intelligence/.
"""
