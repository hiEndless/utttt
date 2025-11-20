import uvicorn
from fastapi import FastAPI
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from agent_server.a2a.cards import get_agent_card
from agent_server.a2a.executors import ExpertAgentExecutor
from agent_server.agents.experts import load_expert


def build_app(agent_name: str) -> FastAPI:
    card = get_agent_card(agent_name)
    executor = ExpertAgentExecutor(load_expert(agent_name), agent_name)
    handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())
    app = A2AStarletteApplication(agent_card=card, http_handler=handler).build()

    async def health(request):
        return JSONResponse({"status": "ok", "agent": agent_name, "url": card.url})

    async def agents(request):
        return JSONResponse(card.model_dump(exclude_none=True, by_alias=True))

    async def debug(request):
        html = """
        <html>
        <head><title>Agent Debug</title></head>
        <body>
        <h3>Agent Debug</h3>
        <p>Send message/send to this agent</p>
        <textarea id=\"input\" rows=\"6\" cols=\"80\">hello</textarea><br/>
        <button onclick=\"send()\">Send</button>
        <pre id=\"out\"></pre>
        <script>
        async function send(){
          const text = document.getElementById('input').value;
          const payload = {
            jsonrpc: "2.0",
            id: 1,
            method: "message/send",
            params: {
              message: {
                kind: "message",
                role: "user",
                messageId: String(Math.random()),
                parts: [{ kind: "text", text }]
              },
              configuration: { blocking: true }
            }
          };
          const res = await fetch("/", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload)});
          document.getElementById('out').textContent = await res.text();
        }
        </script>
        </body>
        </html>
        """
        return HTMLResponse(html)

    app.routes.extend([
        Route("/health", endpoint=health, methods=["GET"]),
        Route("/agents", endpoint=agents, methods=["GET"]),
        Route("/debug", endpoint=debug, methods=["GET"]),
    ])

    return app


def run_server(agent_name: str, host: str = "0.0.0.0", port: int = 10001):
    app = build_app(agent_name)
    uvicorn.run(app, host=host, port=port)


def run_all():
    # This starts only one server; start others in separate processes or terminals
    run_server("technical", port=10001)