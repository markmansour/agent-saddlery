# Diagrams

Mermaid diagrams for the `saddlery` core. They render inline on GitHub and Linear.

| File | Source |
|---|---|
| [class-core.md](class-core.md) | Generated — pyreverse class diagram of `saddlery`. |
| [packages-core.md](packages-core.md) | Generated — pyreverse package diagram of `saddlery`. |
| [events-er.md](events-er.md) | Generated — ER diagram of the event models + `Message`. |
| [echo-loop-sequence.md](echo-loop-sequence.md) | Hand-authored — the 0.1 echo-loop sequence. |
| [tool-round-trip-sequence.md](tool-round-trip-sequence.md) | Hand-authored — the MM-8 tool-calling round-trip. |

## Regenerate

From the repo root:

    make diagrams

which runs `backend/scripts/gen_diagrams.py`. Generated files carry a "do not edit"
banner; edit the generator, not the output. Hand-authored diagrams are edited directly.
