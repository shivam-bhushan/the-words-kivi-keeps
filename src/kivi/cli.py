"""Kivi phonetic memory demo CLI.

    kivi init [--reset]           create / reset the database
    kivi dictate RAW FORMATTED    feed a dictation; see memory-aware output + why
    kivi correct WRONG RIGHT      teach an explicit correction
    kivi memories [--all]         inspect memory state
    kivi show MEMORY_ID           one memory with its evidence trail
    kivi explain DICTATION_ID     replay every decision for a dictation
    kivi history                  recent dictations
    kivi reset                    wipe everything and start over
"""
import typer
from rich.console import Console
from rich.table import Table

from kivi import store
from kivi.db import get_connection, init_db
from kivi.pipeline import DictationResult, learn_correction, process_dictation

app = typer.Typer(help="Kivi phonetic memory: learns your words, fixes your transcripts.")
console = Console()

ACTION_STYLES = {
    "applied": "bold green",
    "learned_correction": "bold green",
    "learned_promoted": "green",
    "learned_candidate": "cyan",
    "learned_ambiguous": "yellow",
    "abstained_low_confidence": "yellow",
    "abstained_ambiguous": "yellow",
    "abstained_common_word": "yellow",
    "abstained_no_match": "dim",
}


def _print_result(result: DictationResult) -> None:
    console.print(f"\n[dim]dictation #{result.dictation_id}[/dim]")
    console.print(f"[dim]raw ASR:      [/dim]{result.raw_asr}")
    console.print(f"[dim]formatted:    [/dim]{result.formatted_text}")
    if result.memory_aware_text != result.formatted_text:
        console.print(f"[bold]memory-aware: [/bold][green]{result.memory_aware_text}[/green]")
    else:
        console.print(f"[bold]memory-aware: [/bold]{result.memory_aware_text} [dim](unchanged)[/dim]")

    if result.decisions:
        console.print("\n[bold]decisions:[/bold]")
        for d in result.decisions:
            style = ACTION_STYLES.get(d.action, "")
            console.print(f"  [{style}]{d.action:26}[/{style}] {d.reason}")
    else:
        console.print("\n[dim]no decisions -- nothing looked personal, nothing matched.[/dim]")


@app.command()
def init(reset: bool = typer.Option(False, "--reset", help="Drop the DB first.")) -> None:
    """Create the database (idempotent)."""
    init_db(reset=reset)
    console.print("[green]database ready.[/green]")


@app.command()
def dictate(
    raw: str = typer.Argument(..., help="Raw ASR output."),
    formatted: str = typer.Argument(..., help="LLM-formatted output."),
    llm: bool = typer.Option(False, "--llm", help="Apply memories via the LLM formatting prompt instead of deterministic replacement."),
) -> None:
    """Process one dictation: apply memories, then learn from it."""
    conn = get_connection()
    try:
        result = process_dictation(conn, raw, formatted)
        category_signals = []
        if llm:
            from kivi.llm import apply_with_llm, relevant_memories
            from kivi.pipeline import record_category_signals

            memories = relevant_memories(formatted, store.get_memories(conn))
            text, categories = apply_with_llm(formatted, memories)
            result.memory_aware_text = text
            store.set_memory_aware_text(conn, result.dictation_id, text)
            category_signals = record_category_signals(
                conn, result.dictation_id, categories, memories)
        _print_result(result)
        if category_signals:
            console.print("\n[bold]category signals (LLM-inferred, low trust "
                          "until repeated or corrected):[/bold]")
            for s in category_signals:
                style = "green" if s.outcome == "promoted" else "dim"
                console.print(f"  [{style}]{s.canonical_form:12} -> {s.category:10} "
                              f"[{s.outcome}][/{style}] {s.reason}")
    finally:
        conn.close()


@app.command()
def correct(
    wrong: str = typer.Argument(..., help="What Kivi wrote."),
    right: str = typer.Argument(..., help="What it should have been."),
    category: str = typer.Option(
        None, "--category",
        help="What kind of term this is (e.g. person, product). Only recorded "
             "if you state it -- never guessed from spelling."),
) -> None:
    """Teach Kivi an explicit correction."""
    conn = get_connection()
    try:
        result = learn_correction(conn, wrong, right, category=category)
        _print_result(result)
    finally:
        conn.close()


@app.command()
def memories(
    show_all: bool = typer.Option(False, "--all", help="Include retired memories."),
) -> None:
    """Inspect current memory state."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM memory_entries" + ("" if show_all else " WHERE status != 'retired'")
            + " ORDER BY status = 'active' DESC, confidence DESC"
        ).fetchall()
        if not rows:
            console.print("[dim]no memories yet.[/dim]")
            return
        table = Table(title="memory entries")
        for col in ("id", "canonical form", "category", "phonetic key", "status", "confidence", "evidence", "last seen"):
            table.add_column(col)
        for r in rows:
            table.add_row(str(r["id"]), r["canonical_form"], r["category"], r["phonetic_key"], r["status"],
                          f"{r['confidence']:.2f}", str(r["evidence_count"]), r["last_seen_at"])
        console.print(table)
    finally:
        conn.close()


@app.command()
def show(memory_id: int) -> None:
    """One memory with its full evidence trail."""
    conn = get_connection()
    try:
        m = conn.execute("SELECT * FROM memory_entries WHERE id = ?", (memory_id,)).fetchone()
        if m is None:
            console.print(f"[red]no memory #{memory_id}[/red]")
            raise typer.Exit(1)
        console.print(f"\n[bold]{m['canonical_form']}[/bold]  ({m['category']}, {m['status']}, "
                      f"confidence {m['confidence']:.2f}, evidence x{m['evidence_count']})")
        console.print(f"[dim]phonetic key {m['phonetic_key']} · created {m['created_at']} "
                      f"· last seen {m['last_seen_at']}[/dim]\n")
        for v in store.get_variants(conn, memory_id):
            src = f"dictation #{v['source_dictation_id']}" if v["source_dictation_id"] else "unknown source"
            console.print(f"  observed '{v['surface_form']}' via {v['signal_type']} ({src}, {v['created_at']})")
        signals = store.get_category_signals(conn, memory_id)
        if signals:
            console.print("\n[dim]category evidence:[/dim]")
            for s in signals:
                src = f"dictation #{s['source_dictation_id']}" if s["source_dictation_id"] else "unknown source"
                console.print(f"  '{s['category']}' via {s['source']} ({src}, {s['created_at']})")
    finally:
        conn.close()


@app.command()
def explain(dictation_id: int) -> None:
    """Replay every decision made for a dictation."""
    conn = get_connection()
    try:
        d = store.get_dictation(conn, dictation_id)
        if d is None:
            console.print(f"[red]no dictation #{dictation_id}[/red]")
            raise typer.Exit(1)
        console.print(f"\n[dim]raw ASR:      [/dim]{d['raw_asr']}")
        console.print(f"[dim]formatted:    [/dim]{d['formatted_text']}")
        console.print(f"[bold]memory-aware: [/bold]{d['memory_aware_text']}")
        decisions = store.get_decisions(conn, dictation_id)
        if not decisions:
            console.print("\n[dim]no decisions recorded.[/dim]")
            return
        console.print("\n[bold]decisions:[/bold]")
        for row in decisions:
            style = ACTION_STYLES.get(row["action"], "")
            console.print(f"  [{style}]{row['action']:26}[/{style}] {row['reason']}")
    finally:
        conn.close()


@app.command()
def history(limit: int = typer.Option(10, help="How many recent dictations.")) -> None:
    """Recent dictations, newest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM dictations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        if not rows:
            console.print("[dim]no dictations yet.[/dim]")
            return
        for r in rows:
            kind = "correction" if r["is_explicit_correction"] else "dictation"
            console.print(f"[bold]#{r['id']}[/bold] [dim]{kind} · {r['created_at']}[/dim]")
            console.print(f"   {r['formatted_text']}")
            if r["memory_aware_text"] and r["memory_aware_text"] != r["formatted_text"]:
                console.print(f"   [green]-> {r['memory_aware_text']}[/green]")
    finally:
        conn.close()


@app.command()
def seed() -> None:
    """Replay seed/observations.jsonl to reach a known memory state."""
    from kivi.seed import load_events, replay

    init_db()
    conn = get_connection()
    try:
        n = replay(conn, load_events())
        console.print(f"[green]replayed {n} seed observations.[/green] "
                      "Run 'kivi memories' to inspect the result.")
    finally:
        conn.close()


@app.command()
def reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Wipe the database and start fresh."""
    if not yes and not typer.confirm("Delete all memories and dictations?"):
        raise typer.Exit()
    init_db(reset=True)
    console.print("[green]reset done.[/green]")


if __name__ == "__main__":
    app()
