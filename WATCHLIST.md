# Watchlist and eligibility

*What the scout watches, and what a launch has to pass before it becomes a test card. Declared up front so selection isn't a vibe.*

## Where the scout looks (every 12h)

- **Hacker News** front page and Show HN (Algolia API, last 24h, points ≥ 50 or a launch from a watched vendor).
- **GitHub trending** (daily, all languages) and releases of watched repos.
- **Vendor changelogs and blogs**: Anthropic, OpenAI, Google (Gemini API, ADK), Mistral, Cohere, Meta (Llama), xAI, DeepSeek, Qwen, Hugging Face, Vercel (AI SDK), LangChain/LangGraph, LlamaIndex, CrewAI, Pydantic (Pydantic AI, Logfire), Microsoft (Semantic Kernel, AutoGen), Cloudflare (Agents, Workers AI), Supabase, Modal, E2B, Daytona, Browserbase, Ollama, Docker (MCP), Stripe (agent toolkit), Replicate, Together, Fireworks, Groq, Cerebras.
- **npm and PyPI**: new major or minor versions of watched packages, and new packages with `mcp`, `agent`, `llm` in the name that cross the HN/GitHub bar above.
- **The MCP registry** (`registry.modelcontextprotocol.io`): new or updated servers from known publishers.

The scout may read anything to decide what's notable. None of that reading reaches the tester (see `SPEC.md` §4).

## Eligibility (all must hold)

1. **Public docs.** A quickstart or getting-started page anyone can read without logging in.
2. **No signup, or a key NJ has provisioned.** v1 tests only tools that need no account. A tool that needs a vendor key is eligible only once NJ has put that key in the tester's key folder and listed it in `keys.json` (name → env var). The scout marks such cards `needs_key` and they wait.
3. **Relevant to people building agents.** SDKs, model APIs, MCP servers, agent frameworks, CLIs, sandboxes, browser and eval tools. Not consumer apps, not research papers without code.
4. **Runnable in the sandbox.** Linux x86-64, no GPU, ≤ 4 GB RAM, ≤ 5 GB download, no hardware, no phone verification, no desktop GUI.
5. **A first task with a checkable outcome.** If the quickstart's first step can't be checked by a command (output, file, exit code), it's not a card.
6. **Notable.** A watched vendor's launch, or ≥ 50 HN points, or ≥ 500 GitHub stars in its first week, or a major version of a package with ≥ 100k weekly downloads.
7. **Not tested in the last 30 days at the same major.minor version.** Re-tests happen for new versions and for 30-day revisits.

## Caps

- Scout: at most 5 new cards per run.
- Tester: at most `MAX_TESTS_PER_DAY` = 3 cards per day, oldest eligible card first, except a watched vendor's launch jumps the queue.
- A card older than 14 days that never ran goes to `cards/skipped/` with the reason.

## Not tested (ever)

- A current sponsor's products.
- Tools whose terms forbid automated use or benchmarking.
- Anything whose quickstart needs payment, KYC or a real phone number.
