# How to Connect to Claude/ChatGPT

This repo exposes an MCP server named `anthropic-news`. It provides mostly read-oriented
research tools for Anthropic news, Claude Code changelogs, docs release notes, GitHub
activity, Hacker News, and Reddit signals, plus local SQLite persistence tools for research
sessions, notes, and generated reports.

The mental model is:

```text
Claude / ChatGPT / Codex
    <-> MCP transport
    <-> anthropic-news-mcp
    <-> Anthropic/news/docs/GitHub/etc.
```

There are two deployment styles:

| Style | Used by | How it connects |
| --- | --- | --- |
| Local stdio MCP | Claude Desktop, Claude Code, Codex CLI | The client launches a local command such as `uvx anthropic-news-mcp`. |
| Remote HTTP MCP | Claude Web, Claude mobile, ChatGPT, Codex CLI, Claude Code | The client connects to a public HTTPS endpoint such as `https://your-domain.com/mcp`. |

For this repo, the local command is:

```bash
uvx anthropic-news-mcp
```

For remote deployments, the ASGI app is:

```text
anthropic_news_mcp.asgi:app
```

and the MCP endpoint is:

```text
/mcp
```

## Current repo caveats

As of 2026-05-08, this repo's remote ASGI mode is intentionally locked down. It refuses
startup unless these environment variables are configured:

```bash
ANTHROPIC_NEWS_MCP_AUTH_ISSUER
ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE
ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS
ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS
```

Optional remote variables:

```bash
ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES
ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL
GITHUB_TOKEN
ANTHROPIC_NEWS_MCP_CACHE_DB
```

That means a simple `ngrok` tunnel will not be enough unless auth, host, and origin settings
also match the client.

For fast local testing with Claude Web or ChatGPT, this repo would need either:

1. A no-auth development mode, for example `ANTHROPIC_NEWS_MCP_AUTH_MODE=none`.
2. A real OAuth/OIDC provider that can issue bearer JWTs accepted by this server.

ChatGPT has one additional compatibility concern. OpenAI's MCP docs distinguish full MCP
developer-mode connectors from search-oriented connectors/deep research. For broad ChatGPT
compatibility, a remote MCP may still need literal `search` and `fetch` adapter tools. This
repo currently exposes a richer MCP-native research surface:

```text
ping
list_sources
get_recent_updates
search_updates
get_source_health
get_update_detail
search_web_sources
get_timeline
compare_updates
build_digest_context
create_research_session
save_research_note
save_research_report
get_research_session
evaluate_claims
```

Developer-mode ChatGPT may be able to use the full tool surface, but ChatGPT deep research
and search-style connector flows are likely to work better if this repo adds `search` and
`fetch` adapter tools that wrap `search_web_sources` and `get_update_detail`.

## Current research workflows

For Claude Desktop, Claude Code, Codex, and full MCP developer-mode clients, the recommended
workflow is:

```text
list_sources
  -> search_web_sources or get_recent_updates
  -> get_update_detail for citation-grade page text and excerpts
  -> build_digest_context or get_timeline for grouped evidence
  -> evaluate_claims when checking a draft answer
  -> create_research_session / save_research_note / save_research_report when persistence is useful
```

The server does not generate final prose by itself. It returns evidence packages, excerpts,
URLs, retrieved timestamps, content hashes, timelines, and support labels so the client model
can write grounded summaries with citations.

The useful prompt workflows are:

```text
latest_update_digest
source_health_report
weekly_category_digest
generate_digest
verify_claims_against_evidence
research_session_brief
```

Official references:

- OpenAI remote MCP overview: https://platform.openai.com/docs/mcp/
- OpenAI ChatGPT developer mode: https://platform.openai.com/docs/developer-mode
- OpenAI Codex MCP setup example: https://platform.openai.com/docs/docs-mcp
- Anthropic custom connectors: https://support.anthropic.com/en/articles/11175166-getting-started-with-custom-integrations-using-remote-mcp
- Claude Code MCP docs: https://docs.anthropic.com/en/docs/claude-code/mcp

## Claude Desktop

Claude Desktop can run this MCP locally over stdio. This is the simplest Claude setup.

Edit:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add:

```json
{
  "mcpServers": {
    "anthropic-news": {
      "command": "uvx",
      "args": ["anthropic-news-mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_optional_token"
      }
    }
  }
}
```

Then restart Claude Desktop.

Ask:

```text
List the Anthropic News sources.
```

or:

```text
Use Anthropic News to find recent Claude Code updates.
```

If Claude Desktop already has a Python environment with this repo installed from source,
you can also use:

```json
{
  "mcpServers": {
    "anthropic-news": {
      "command": "python",
      "args": ["-m", "anthropic_news_mcp"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_optional_token"
      }
    }
  }
}
```

## Claude Web App

Claude Web cannot launch your local `uvx anthropic-news-mcp` command. It needs a remote MCP
server reachable from Anthropic's cloud infrastructure.

Architecture:

```text
Claude Web
    -> Custom Connector
    -> https://your-domain.com/mcp
    -> anthropic-news-mcp
```

Install remote dependencies:

```bash
pip install "anthropic-news-mcp[remote]"
```

Run the ASGI app:

```bash
export ANTHROPIC_NEWS_MCP_AUTH_ISSUER="https://issuer.example"
export ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE="anthropic-news"
export ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES="anthropic-news:read"
export ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS="mcp.example.com"
export ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS="https://claude.ai"
export ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL="https://mcp.example.com"
uvicorn anthropic_news_mcp.asgi:app --host 0.0.0.0 --port 8000
```

Then expose it at:

```text
https://mcp.example.com/mcp
```

For individual Claude Pro or Max plans:

1. Open `https://claude.ai`.
2. Go to `Customize` -> `Connectors`.
3. Click `+` or `Add custom connector`.
4. Enter the remote MCP URL: `https://mcp.example.com/mcp`.
5. Add OAuth client settings if your deployment requires them.
6. Add the connector.
7. Enable it in a conversation from the connector picker.

For Team or Enterprise plans, an owner usually adds the connector under organization
settings first, then members connect to it individually.

## Claude Phone App

Claude mobile uses remote connectors through your Claude account. It does not run local
stdio MCP commands from your phone.

Use this path:

```text
Claude mobile app
    -> Claude account connector
    -> https://your-domain.com/mcp
    -> anthropic-news-mcp
```

Recommended setup:

1. Add the custom connector from Claude Web first.
2. Confirm it works in a Claude Web conversation.
3. Open Claude on your phone.
4. Start a new chat and look for the connector/tool picker.
5. Enable the Anthropic News connector for that conversation.

If the connector does not appear on mobile, use Claude Web or Claude Desktop for the same
remote connector. Mobile connector UI can lag behind web rollout.

## Claude Code

Claude Code can use either local stdio MCP or remote HTTP MCP.

Local stdio setup:

```bash
claude mcp add anthropic-news -- uvx anthropic-news-mcp
```

With an optional GitHub token:

```bash
claude mcp add anthropic-news \
  --env GITHUB_TOKEN=ghp_your_optional_token \
  -- uvx anthropic-news-mcp
```

Project-shared setup:

```bash
claude mcp add anthropic-news --scope project -- uvx anthropic-news-mcp
```

That creates or updates a project `.mcp.json`.

Remote HTTP setup:

```bash
claude mcp add --transport http anthropic-news https://mcp.example.com/mcp
```

If the remote server needs a bearer token:

```bash
claude mcp add --transport http anthropic-news https://mcp.example.com/mcp \
  --header "Authorization: Bearer your-token"
```

If it uses OAuth, add the remote server and then run this inside Claude Code:

```text
/mcp
```

Verify:

```bash
claude mcp list
claude mcp get anthropic-news
```

Try:

```text
Use anthropic-news to summarize recent Claude Code updates.
```

## ChatGPT Web App

ChatGPT does not run your local `uvx anthropic-news-mcp` command. It needs a remote MCP
server reachable over HTTPS.

Architecture:

```text
ChatGPT
    -> Custom MCP connector / app
    -> https://your-domain.com/mcp
    -> anthropic-news-mcp
```

Remote server setup is the same ASGI path:

```bash
pip install "anthropic-news-mcp[remote]"

export ANTHROPIC_NEWS_MCP_AUTH_ISSUER="https://issuer.example"
export ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE="anthropic-news"
export ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES="anthropic-news:read"
export ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS="mcp.example.com"
export ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS="https://chatgpt.com"
export ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL="https://mcp.example.com"

uvicorn anthropic_news_mcp.asgi:app --host 0.0.0.0 --port 8000
```

Expose it at:

```text
https://mcp.example.com/mcp
```

For local HTTPS testing, use a tunnel:

```bash
ngrok http 8000
```

Then the endpoint is:

```text
https://abc123.ngrok-free.app/mcp
```

For this repo's current remote auth checks, set:

```bash
export ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS="abc123.ngrok-free.app"
export ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS="https://chatgpt.com"
export ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL="https://abc123.ngrok-free.app"
```

You still need a compatible issuer/audience/token flow unless the repo adds a no-auth
development mode.

In ChatGPT:

1. Open ChatGPT on the web.
2. Go to `Settings`.
3. Open `Connectors` or `Apps`.
4. Enable `Developer mode` under advanced settings if your plan/workspace supports it.
5. Create or import a custom MCP connector/app.
6. Enter the MCP server URL: `https://mcp.example.com/mcp`.
7. Complete OAuth/authentication if prompted.
8. Enable it from the composer tool picker.

Try:

```text
Use Anthropic News to find recent Claude Code updates.
```

If ChatGPT imports the server but does not use it well, add ChatGPT adapter tools:

```text
search(query) -> wraps search_web_sources(query)
fetch(id) -> wraps get_update_detail(id)
```

OpenAI's search/deep-research MCP examples expect those names and result shapes.

## ChatGPT Desktop App

Treat ChatGPT Desktop like ChatGPT Web for MCP purposes. It does not launch this local
Python MCP server as a stdio process.

Recommended path:

1. Configure the remote MCP connector in ChatGPT Web.
2. Confirm it works in a web conversation.
3. Open ChatGPT Desktop.
4. Use the same account/workspace.
5. Enable the connector from the composer tool picker if it appears.

If the connector is unavailable in Desktop, use ChatGPT Web. MCP developer-mode rollout and
UI availability can differ between ChatGPT clients.

## ChatGPT Phone App

ChatGPT mobile does not run local stdio MCP servers. Use the account-level remote connector
path:

```text
ChatGPT mobile app
    -> ChatGPT account/workspace connector
    -> https://your-domain.com/mcp
    -> anthropic-news-mcp
```

Recommended path:

1. Configure and test the MCP connector in ChatGPT Web.
2. Open ChatGPT on your phone with the same account/workspace.
3. Check whether the connector appears in the tool picker.
4. If it does not appear, use ChatGPT Web for MCP testing.

## Codex

Codex can connect to MCP servers from the CLI or IDE extension. The Codex CLI stores MCP
configuration in shared Codex config.

Remote HTTP setup:

```bash
codex mcp add anthropic-news --url https://mcp.example.com/mcp
codex mcp list
```

Equivalent `~/.codex/config.toml`:

```toml
[mcp_servers.anthropic-news]
url = "https://mcp.example.com/mcp"
```

Local stdio setup:

```bash
codex mcp add anthropic-news -- uvx anthropic-news-mcp
codex mcp list
```

If you want to point Codex at a local HTTP server during development, Codex must be able to
reach that URL from wherever it is running. Local Codex CLI can usually reach localhost:

```bash
codex mcp add anthropic-news-local --url http://localhost:8000/mcp
```

Cloud or sandboxed Codex environments usually need a public HTTPS URL instead:

```bash
codex mcp add anthropic-news --url https://abc123.ngrok-free.app/mcp
```

## Remote deployment checklist

1. Install remote dependencies:

   ```bash
   pip install "anthropic-news-mcp[remote]"
   ```

2. Configure auth and transport security:

   ```bash
   export ANTHROPIC_NEWS_MCP_AUTH_ISSUER="https://issuer.example"
   export ANTHROPIC_NEWS_MCP_AUTH_AUDIENCE="anthropic-news"
   export ANTHROPIC_NEWS_MCP_REQUIRED_SCOPES="anthropic-news:read"
   export ANTHROPIC_NEWS_MCP_ALLOWED_HOSTS="mcp.example.com"
   export ANTHROPIC_NEWS_MCP_ALLOWED_ORIGINS="https://claude.ai,https://chatgpt.com"
   export ANTHROPIC_NEWS_MCP_RESOURCE_SERVER_URL="https://mcp.example.com"
   ```

3. Run:

   ```bash
   uvicorn anthropic_news_mcp.asgi:app --host 0.0.0.0 --port 8000
   ```

4. Put it behind HTTPS:

   ```text
   https://mcp.example.com/mcp
   ```

5. Register that URL in Claude, ChatGPT, Claude Code, or Codex.

6. Test with a minimal prompt:

   ```text
   List available Anthropic News sources.
   ```

7. Then test the main workflow:

   ```text
   Search recent updates about Claude Code.
   ```

## Troubleshooting

If the client says no tools are available:

- Confirm the URL ends in `/mcp`.
- Confirm the server is reachable over HTTPS from the client vendor's cloud.
- Confirm allowed host matches the public domain exactly.
- Confirm allowed origin includes the client, for example `https://claude.ai` or `https://chatgpt.com`.
- Confirm the client is sending a valid bearer token with the expected issuer, audience, and scope.
- Check the ASGI server logs for startup or handshake errors.

If local stdio clients cannot start the server:

- Confirm `uvx anthropic-news-mcp` works in a terminal.
- Confirm Python 3.11 or newer is available.
- Add `GITHUB_TOKEN` only if you need higher GitHub rate limits.
- Restart the client after editing MCP config.

If ChatGPT connects but gives weak results:

- Add `search` and `fetch` adapter tools.
- Keep tool descriptions explicit.
- Return stable IDs, titles, URLs, and concise text for citation.
- Use `search_web_sources`, `get_update_detail`, `build_digest_context`, and `evaluate_claims` for research workflows.
- Keep fetch/evidence tools read-only; expose session, note, and report persistence as intentional local write actions.

## Recommended path for this repo

1. Use Claude Desktop or Claude Code locally first with `uvx anthropic-news-mcp`.
2. Add and test a no-auth development mode only for local tunnel testing, or configure real OAuth/OIDC.
3. Test remote Streamable HTTP with `ngrok` or Cloudflare Tunnel.
4. Connect Claude Web using `https://.../mcp`.
5. Add `search` and `fetch` adapter tools before relying on ChatGPT deep research.
6. Connect ChatGPT Web in developer mode.
7. Deploy to stable hosting such as Fly.io, Render, Railway, EC2, or another ASGI-capable host.
8. Use OAuth/OIDC for any shared or production connector.
