# Watchlist and eligibility

*What the scout watches, and what a launch has to pass before it becomes a test card. Declared up front so selection isn't a vibe.*

## Where the scout looks (every 12h)

- **Hacker News** front page and Show HN (Algolia API, last 24h, points ≥ 50 or a launch from a watched vendor).
- **GitHub trending** (daily, all languages) and releases of watched repos.
- **Vendor changelogs and blogs**: Anthropic, OpenAI, Google (Gemini API, ADK), Mistral, Cohere, Meta (Llama), xAI, DeepSeek, Qwen, Hugging Face, Vercel (AI SDK), LangChain/LangGraph, LlamaIndex, CrewAI, Pydantic (Pydantic AI, Logfire), Microsoft (Semantic Kernel, AutoGen), Cloudflare (Agents, Workers AI), Supabase, Modal, E2B, Daytona, Browserbase, Ollama, Docker (MCP), Stripe (agent toolkit), Replicate, Together, Fireworks, Groq, Cerebras.
- **npm and PyPI**: new major or minor versions of watched packages, and new packages with `mcp`, `agent`, `llm` in the name that cross the HN/GitHub bar above.
- **The MCP registry** (`registry.modelcontextprotocol.io`): new or updated servers from known publishers.

The scout may read anything to decide what's notable. None of that reading reaches the tester (see `SPEC.md`, "Docs only").

## Eligibility (all must hold)

1. **Public docs.** A quickstart or getting-started page anyone can read without logging in.
2. **Credential-free quickstart (v1).** The quickstart's first task runs without any account, API key or login: local SDKs, MCP servers, CLIs, frameworks with a local example, open-weight runtimes small enough for the box. Launches that need a key are still carded (`status: needs_key`) as coverage data, never tested with a substitute or fake call, and never get a verdict. Keyed tests come later as a separately labelled track.
3. **Relevant to people building agents.** SDKs, model APIs, MCP servers, agent frameworks, CLIs, sandboxes, browser and eval tools. Not consumer apps, not research papers without code.
4. **Runnable in the sandbox.** Linux x86-64, no GPU, ≤ 4 GB RAM, ≤ 5 GB download, no hardware, no phone verification, no desktop GUI.
5. **A first task with a checkable outcome.** If the quickstart's first step can't be checked by a command (output, file, exit code), it's not a card.
6. **Notable, by one of three routes** (so incumbents don't win by default):
   - **Launch:** a watched vendor's release, ≥ 50 HN points, ≥ 500 GitHub stars in the first week, or a new major/minor of a package with ≥ 100k weekly downloads.
   - **Backlog:** a mature tool from the backlog below that builders use and we haven't tested (one per scout run when there's room).
   - **Nomination:** a reader or maker opens a "Nominate a tool" issue; it needs a public quickstart and one 👍 from someone other than the maker.
7. **Not tested in the last 30 days at the same major.minor version.** Re-tests happen for new versions and for 30-day revisits.

## Caps and balance

- Scout: at most 5 new cards per run; aim for at least 3 that are runnable (credential-free).
- At most 2 cards per vendor per week. At least one card per run from outside the watched vendors when one qualifies.
- Tester: at most `MAX_TESTS_PER_DAY` = 3 cards a day, oldest eligible first (age, not vendor, sets priority).
- A card older than 14 days that never ran moves to `cards/skipped/` with the reason. Skipped cards and their reasons are public, like the queue.

## Backlog (mature tools, credential-free first task)

FastMCP, the MCP Python and TypeScript SDKs, MCP Inspector, Playwright MCP, Ollama's Python client against a tiny model, LiteLLM's local proxy config check, Chroma, LanceDB, DuckDB's Python API, Pydantic, instructor's offline examples, LangGraph's local graph example, smolagents' tool definitions, uv itself, Hugging Face `transformers` with a tiny model, sentence-transformers with a small model, Outlines with a tiny model, CrewAI's tool decorators, Logfire's local console exporter.

## Not tested (ever)

- A current sponsor's products.
- Tools whose terms forbid automated use or benchmarking.
- Anything whose quickstart needs payment, KYC or a real phone number.
