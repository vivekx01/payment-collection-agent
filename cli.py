from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from agent import Agent


def main():
    console = Console()
    console.print(Panel(
        Text("Payment Collection Agent", justify="center", style="bold white"),
        style="bold blue",
        subtitle="Type 'quit' or 'exit' to end",
    ))
    console.print()

    agent = Agent()

    # Kick off with a greeting
    result = agent.next("Hello")
    console.print(f"[bold cyan]Agent:[/] {result['message']}\n")

    while True:
        try:
            user_input = console.input("[bold green]You:[/] ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                console.print("\n[dim]Session ended.[/]")
                break

            result = agent.next(user_input)
            console.print(f"\n[bold cyan]Agent:[/] {result['message']}\n")

            if agent._initialized:
                snapshot = agent._graph.get_state(agent._config)
                if snapshot.values.get("conversation_ended", False):
                    break

        except KeyboardInterrupt:
            console.print("\n\n[dim]Session ended.[/]")
            break


if __name__ == "__main__":
    main()
